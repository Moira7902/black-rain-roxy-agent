"""Run the ROXY v0.3 rule suite or collect dialogue evidence."""

from __future__ import annotations

import argparse
import ast
from collections import Counter
from copy import deepcopy
from datetime import datetime, timezone
from hashlib import sha256
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
from time import perf_counter
from types import SimpleNamespace

from dataset.validate_dataset import check, execute_rule, module, value_at
from render_report import write_report


ROOT = Path(__file__).resolve().parent
DATA = ROOT / "dataset"
PILOT = (
    "RXY-D002", "RXY-D013", "RXY-D017", "RXY-D023", "RXY-D026", "RXY-D028",
    "RXY-D032", "RXY-D034", "RXY-D036", "RXY-D041", "RXY-Q002", "RXY-Q003",
)


def load_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def git_head(path):
    if not (path / ".git").exists():
        return None
    try:
        return subprocess.run(
            ["git", "-C", str(path), "rev-parse", "HEAD"],
            capture_output=True, text=True, check=True, timeout=5,
        ).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return None


def identify_product(path, live, strict_baseline):
    lock = load_json(ROOT / "product_lock.json")
    fingerprints = {}
    differences = []
    for name, digest in lock["files"].items():
        if not live and name not in {"game_logic.py", "memory_manager.py"}:
            continue
        file = path / name
        if not file.is_file():
            raise ValueError(f"缺少被测文件 {name}。请确认 --product-dir 指向罗希项目的根目录。")
        content = file.read_text(encoding="utf-8").rstrip("\n")
        actual = sha256(content.encode("utf-8")).hexdigest()
        fingerprints[name] = actual
        if actual != digest:
            differences.append(name)
    if differences and strict_baseline:
        raise ValueError(f"与基线 {lock['commit']} 不同的文件：{', '.join(differences)}。")
    head = git_head(path)
    return {
        "baseline_commit": lock["commit"],
        "product_commit": head,
        "baseline_files_match": not differences,
        "files_different_from_baseline": differences,
        "product_file_sha256": fingerprints,
    }


def app_turn(app_path, globals_for_turn):
    # Load the app's turn function without initializing the Streamlit page.
    tree = ast.parse(app_path.read_text(encoding="utf-8-sig"), filename=str(app_path))
    turn = next((node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == "process_turn"), None)
    if turn is None:
        raise ValueError("app.py 中找不到 process_turn。当前版本的对话入口需要适配。")
    unit = ast.Module(body=[turn], type_ignores=[])
    exec(compile(unit, str(app_path), "exec"), globals_for_turn)
    return globals_for_turn["process_turn"]


class DialogueProbe:
    def __init__(self, path, game, memory):
        spec = importlib.util.spec_from_file_location("roxy_eval_npc_agent_core", path / "npc_agent_core.py")
        self.core = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = self.core
        spec.loader.exec_module(self.core)
        self.send = self.core.client.chat.completions.create
        self.core.client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=self.capture_response)))
        self.session = SimpleNamespace()
        scope = {
            "st": SimpleNamespace(session_state=self.session),
            "safe_call_npc_agent": self.capture_normalized,
            "suspicion_stage": game.suspicion_stage,
            "apply_turn_rules": game.apply_turn_rules,
            "enforce_emotion": game.enforce_emotion,
            "GOOD_ENDING": game.GOOD_ENDING,
            "BAD_ENDING": game.BAD_ENDING,
            "add_long_term_memory": memory.add_long_term_memory,
            "add_recent_turn": memory.add_recent_turn,
        }
        self.process_turn = app_turn(path / "app.py", scope)

    def capture_response(self, **kwargs):
        started = perf_counter()
        self.observation["request_started"] = True
        try:
            response = self.send(**kwargs)
        except Exception as exc:
            self.observation.update(provider_error=type(exc).__name__, http_status=getattr(exc, "status_code", None))
            raise
        finally:
            self.observation["model_call_ms"] = round((perf_counter() - started) * 1000, 2)

        choice = response.choices[0] if response.choices else None
        raw = choice.message.content if choice is not None else None
        self.observation.update(raw_reply=raw, finish_reason=choice.finish_reason if choice is not None else None)
        usage = getattr(response, "usage", None)
        if usage is not None:
            self.observation["usage"] = {key: getattr(usage, key, None)
                                         for key in ("prompt_tokens", "completion_tokens", "total_tokens")}
        try:
            parsed = json.loads(raw) if raw else None
            self.observation["raw_json_valid"] = bool(raw)
        except (TypeError, ValueError):
            parsed = None
            self.observation["raw_json_valid"] = False
        try:
            self.core.NPCOutput.model_validate(parsed, strict=True)
            self.observation["raw_schema_valid"] = True
        except self.core.ValidationError:
            self.observation["raw_schema_valid"] = False
        return response

    def capture_normalized(self, player_text, state):
        result, error = self.core.safe_call_npc_agent(player_text, state)
        self.normalized = deepcopy(result)
        # The app's provider error text can contain credentials or request details.
        self.observation["agent_error"] = bool(error or result is None)
        return result, error

    def run(self, case, initial):
        self.session.game_state = deepcopy(initial)
        self.session.last_output = None
        self.session.last_events = []
        turns = []
        for step in case["steps"]:
            if self.session.game_state.get("ending"):
                break
            before = deepcopy(self.session.game_state)
            self.observation = {}
            self.normalized = None
            started = perf_counter()
            try:
                self.process_turn(step["player_input"])
            except Exception as exc:
                self.observation["processing_error"] = type(exc).__name__
            elapsed = round((perf_counter() - started) * 1000, 2)
            after = deepcopy(self.session.game_state)
            advanced = after["turn_count"] > before["turn_count"]
            turns.append({
                **step, "state_before": before, "state_after": after,
                "observation": self.observation, "normalized": self.normalized,
                "displayed": deepcopy(self.session.last_output) if advanced else None,
                "events": deepcopy(self.session.last_events) if advanced else [],
                "turn_processing_ms": elapsed, "advanced": advanced,
            })
            if not advanced or self.observation.get("processing_error"):
                break
        complete = len(turns) == len(case["steps"]) and all(
            t["advanced"] and not t["observation"].get("processing_error") for t in turns)
        last = turns[-1] if turns else {}
        checks = evaluate(case, {
            "observation": last.get("observation"),
            "normalized": last.get("normalized"),
            "final": last.get("state_after") if complete else None,
        })
        if complete:
            status = "check_failed" if any(c["status"] != "passed" for c in checks) else "ready_for_review"
        else:
            status = "incomplete"
        return {
            "case_id": case["case_id"], "case_type": case["case_type"], "status": status,
            "checks": checks, "turns": turns, "missing_steps": [s["step_id"] for s in case["steps"][len(turns):]],
            "model": self.core.DEEPSEEK_MODEL, "ready_for_judge": complete,
        }


def evaluate(case, phases):
    results = []
    for spec in case["checks"]:
        phase = phases.get(spec["phase"])
        result = dict(spec)
        try:
            observed = value_at(phase, spec["path"])
            result.update(status="passed" if check(phase, spec) else "failed", observed=observed)
        except (KeyError, IndexError, TypeError):
            result["status"] = "not_observed"
        results.append(result)
    return results


def rule_result(case, profiles, game, memory):
    final = execute_rule(case, profiles, game, memory)
    checks = evaluate(case, {"final": final})
    return {
        "case_id": case["case_id"], "case_type": case["case_type"],
        "status": "passed" if checks and all(c["status"] == "passed" for c in checks) else "check_failed",
        "checks": checks, "final_state": final,
    }


def judge_input(case, result, rubrics, references):
    def state_fields(state):
        return {key: state.get(key) for key in ("suspicion", "quest_flags", "inventory", "ending", "long_term_memories")}

    turns = result["turns"]
    return {
        "case_id": case["case_id"], "title": case["title"], "setup": case["setup_note"],
        "must": case["must"], "must_not": case["must_not"],
        "rubrics": {key: rubrics[key] for key in case["rubric_ids"]},
        "references": references,
        "starting_history": turns[0]["state_before"].get("recent_history", []),
        "turns": [{
            "step_id": turn["step_id"], "player_input": turn["player_input"],
            "before": state_fields(turn["state_before"]), "after": state_fields(turn["state_after"]),
            "normalized": turn["normalized"], "displayed": turn["displayed"],
            "observation": {key: turn["observation"].get(key) for key in ("raw_json_valid", "raw_schema_valid")},
        } for turn in turns],
    }


def write_line(file, record):
    file.write(json.dumps(record, ensure_ascii=False) + "\n")
    file.flush()


def select_cases(cases, suite, explicit):
    if explicit:
        by_id = {case["case_id"]: case for case in cases}
        unknown = [case_id for case_id in explicit if case_id not in by_id]
        if unknown:
            raise ValueError(f"未知用例编号：{', '.join(unknown)}")
        return [by_id[case_id] for case_id in dict.fromkeys(explicit)]
    if suite == "pilot":
        return select_cases(cases, suite, PILOT)
    return [c for c in cases if suite == "all" or c["case_type"] == (
        "deterministic" if suite == "rules" else "dialogue")]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--product-dir", type=Path, required=True, help="罗希项目的根目录")
    parser.add_argument("--suite", choices=["rules", "pilot", "dialogue", "all"], default="rules")
    parser.add_argument("--case", action="append", help="只跑指定编号，可重复")
    parser.add_argument("--live", action="store_true", help="允许对话用例调用项目配置的模型")
    parser.add_argument("--strict-baseline", action="store_true", help="所用文件与基线不同时退出")
    parser.add_argument("--out", type=Path, help="新的运行目录")
    args = parser.parse_args()
    product = args.product_dir.resolve()
    cases = [json.loads(line) for line in (DATA / "cases.jsonl").read_text(encoding="utf-8").splitlines() if line]
    manifest = load_json(DATA / "manifest.json")
    profiles = load_json(DATA / "profiles.json")
    rubrics = load_json(DATA / "rubrics.json")
    try:
        selected = select_cases(cases, args.suite, args.case)
        live_needed = any(c["case_type"] == "dialogue" and c["selection_status"] == "eligible" for c in selected)
        if live_needed and not args.live:
            raise ValueError("选中了对话用例。请在本地配好凭证后加 --live，或先跑 --suite rules。")
        version = identify_product(product, live_needed, args.strict_baseline)
        game = module(product, "game_logic")
        memory = module(product, "memory_manager")
        probe = DialogueProbe(product, game, memory) if live_needed else None
        references = {
            "world": probe.core.WORLD_LORE,
            "role": probe.core.ROXY_PROFILE,
            "author_decisions": manifest["author_canon"],
        } if probe else {}
        date = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
        out = (args.out or Path("runs") / date).resolve()
        out.mkdir(parents=True, exist_ok=False)
    except (OSError, ValueError, ImportError, RuntimeError) as exc:
        parser.exit(2, f"启动失败：{exc}\n")

    summary = {
        "dataset_version": manifest["version"], **version, "suite": "custom" if args.case else args.suite,
        "selected_cases": [c["case_id"] for c in selected], "model": probe.core.DEEPSEEK_MODEL if probe else None,
        "scope": "rule_functions_and_app_turn_logic", "browser_tested": False, "judge_called": False,
    }
    if version["files_different_from_baseline"]:
        print("以下文件与基线不同，本次测试使用本地版本：" + "、".join(version["files_different_from_baseline"]))
    counts = Counter()
    with (out / "results.jsonl").open("w", encoding="utf-8") as evidence, \
         (out / "judge_inputs.jsonl").open("w", encoding="utf-8") as judges:
        for case in selected:
            if case["selection_status"] != "eligible" or case["case_type"] not in {"dialogue", "deterministic"}:
                result = {"case_id": case["case_id"], "case_type": case["case_type"],
                          "status": "not_run", "reason": "requires_separate_runtime_or_browser_test"}
            elif case["case_type"] == "deterministic":
                result = rule_result(case, profiles, game, memory)
            else:
                result = probe.run(case, profiles[case["profile_id"]])
            write_line(evidence, result)
            if result.get("ready_for_judge"):
                write_line(judges, judge_input(case, result, rubrics, references))
            counts[result["status"]] += 1
    summary["statuses"] = dict(counts)
    (out / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"运行目录：{out}\n" + json.dumps(summary["statuses"], ensure_ascii=False))
    try:
        print(f"报告：{write_report(out, cases)}")
    except (OSError, ValueError) as exc:
        print(f"无法生成报告：{exc}", file=sys.stderr)
    return int(bool(counts["check_failed"] or counts["incomplete"]))


if __name__ == "__main__":
    raise SystemExit(main())
