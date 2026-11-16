"""Render saved ROXY evaluation results as a self-contained HTML report."""

from __future__ import annotations

import argparse
from collections import Counter
from html import escape
import json
from pathlib import Path


CASE_LABELS = {
    "check_failed": "检查未通过",
    "incomplete": "对话未走完",
    "ready_for_review": "已采集，待评分",
    "passed": "规则通过",
    "not_run": "未运行",
}
CHECK_LABELS = {"passed": "符合预期", "failed": "不符合预期", "not_observed": "未取得数据"}
PHASE_LABELS = {"final": "最终状态", "normalized": "规范化输出", "observation": "原始回包"}
OPS = {"eq": "等于", "neq": "不等于", "not_in": "不在列表中", "length_eq": "长度等于",
       "contains": "包含", "not_contains": "不包含", "contains_record": "包含记录",
       "not_contains_record": "不包含记录"}
STYLES = """
:root{color-scheme:light;--ink:#262124;--muted:#63575c;--red:#a3223a;--line:#e9dfe2;--paper:#fff}
*{box-sizing:border-box}
body{margin:0;background:#f7f4f5;color:var(--ink);font:16px/1.65 Inter,"Microsoft YaHei","PingFang SC",system-ui,sans-serif}
header{background:#231c20;color:white;border-bottom:4px solid var(--red)}
header div,main{max-width:1020px;margin:auto;padding:1.75rem 1.5rem}
h1,h2,h3,p{margin:0}
h1{font-size:clamp(1.6rem,4vw,2.35rem);line-height:1.2}
header p{color:#eddee3;margin-top:.55rem;font-size:.92rem;overflow-wrap:anywhere}
main{padding-bottom:3rem}
.metrics{display:flex;gap:.6rem;flex-wrap:wrap;margin:0 0 1.35rem}
.metric{background:var(--paper);border:1px solid var(--line);padding:.45rem .85rem;border-radius:8px}
.metric strong{font-variant-numeric:tabular-nums;margin-right:.4em}
h2{font-size:1.23rem;margin-bottom:.55rem}
nav{margin:0 0 1.4rem}
nav ul{display:flex;flex-wrap:wrap;gap:.4rem 1.15rem;list-style:none;margin:0;padding:0}
a{color:#8c1d32;text-underline-offset:3px}
article{background:var(--paper);border:1px solid var(--line);border-radius:10px;margin:0 0 .85rem;padding:1rem 1.15rem}
article:target{outline:2px solid var(--red)}
.case-head{display:flex;justify-content:space-between;align-items:start;gap:.4rem 1rem;flex-wrap:wrap}
.case-head h3{font-size:1.08rem;overflow-wrap:anywhere}
.case-id{color:var(--muted);font-size:.84rem;margin-right:.55rem}
.badge{white-space:nowrap;font-size:.8rem;font-weight:650;border-radius:5px;padding:.14rem .45rem;background:#eee9ec;color:#4b4148}
.bad{color:#941f34;background:#fce7eb}
.good{color:#235c3d;background:#e6f3eb}
.turn{border-top:1px solid var(--line);margin-top:.7rem;padding-top:.7rem}
.round,.meta{color:var(--muted);font-size:.88rem}
.round{font-weight:650}
.exchange{display:grid;grid-template-columns:6rem minmax(0,1fr);gap:.24rem .65rem;margin:.35rem 0}
.exchange dt{font-weight:650}
.exchange dd{margin:0;white-space:pre-wrap;overflow-wrap:anywhere}
.meta{overflow-wrap:anywhere}
.table-scroll{overflow:auto;margin:.7rem 0 .15rem}
table{border-collapse:collapse;width:100%;font-size:.9rem}
th,td{text-align:left;padding:.36rem .5rem;border-bottom:1px solid var(--line);vertical-align:top}
td{overflow-wrap:anywhere}
th{background:#f8f4f5}
.check-fail td{background:#fff2f4}
details{margin:.55rem 0 0}
summary{cursor:pointer;color:#6e2434;font-size:.88rem;font-weight:650}
pre{white-space:pre-wrap;overflow-wrap:anywhere;background:#f8f5f6;border-radius:5px;padding:.65rem .8rem;font-size:.83rem}
code,pre{font-family:"IBM Plex Mono",Consolas,monospace}
@media(max-width:580px){header div,main{padding:1.1rem .7rem}article{padding:.8rem}.exchange{grid-template-columns:1fr;gap:0}.exchange dd{margin-bottom:.35rem}.table-scroll table{min-width:520px}}
"""


def read_lines(path):
    rows = []
    with path.open(encoding="utf-8-sig") as file:
        for line_no, line in enumerate(file, 1):
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"{path.name} 第 {line_no} 行不是完整的 JSON。") from exc
            if not isinstance(row, dict) or "case_id" not in row:
                raise ValueError(f"{path.name} 第 {line_no} 行缺少用例编号。")
            rows.append(row)
    return rows


def show(value):
    if isinstance(value, str):
        return escape(value)
    return escape(json.dumps(value, ensure_ascii=False))


def details(label, value, *, raw=False):
    if value is None or value == "":
        return ""
    body = value if raw and isinstance(value, str) else json.dumps(value, ensure_ascii=False, indent=2)
    return f"<details><summary>{escape(label)}</summary><pre>{escape(body)}</pre></details>"


def render_checks(checks):
    if not checks:
        return ""
    rows = []
    for check in sorted(checks, key=lambda item: item.get("status") == "passed"):
        status = check.get("status", "not_observed")
        row_class = ' class="check-fail"' if status != "passed" else ""
        phase = check.get("phase", "")
        op = check.get("op", "")
        expected = f"{show(OPS.get(op, op))} {show(check['value'])}" if "value" in check else show(OPS.get(op, op))
        observed = show(check["observed"]) if "observed" in check else "未取得"
        rows.append(
            f"<tr{row_class}><td>{show(PHASE_LABELS.get(phase, phase))} <code>{show(check.get('path', ''))}</code></td>"
            f"<td>{expected}</td><td>{observed}</td><td>{show(CHECK_LABELS.get(status, status))}</td></tr>"
        )
    return (
        '<div class="table-scroll"><table><thead><tr><th scope="col">自动检查</th><th scope="col">预期</th>'
        '<th scope="col">实际</th><th scope="col">结果</th></tr></thead><tbody>'
        + "".join(rows) + "</tbody></table></div>"
    )


def render_turn(turn, number):
    displayed = turn.get("displayed") or {}
    observation = turn.get("observation") or {}
    before = turn.get("state_before") or {}
    after = turn.get("state_after") or {}
    timing = observation.get("model_call_ms")
    summary = []
    if "suspicion" in before and "suspicion" in after:
        summary.append(f"警惕值 {before['suspicion']} → {after['suspicion']}")
    if timing is not None:
        summary.append(f"模型耗时 {timing} ms")
    if after.get("ending"):
        summary.append(f"结局 {after['ending']}")
    for key, label in (("provider_error", "接口错误"), ("processing_error", "处理错误")):
        if observation.get(key):
            summary.append(f"{label} {observation[key]}")
    if observation.get("raw_json_valid") is False:
        summary.append("原始回复无法解析为 JSON")
    if observation.get("raw_schema_valid") is False and observation.get("raw_json_valid") is True:
        summary.append("原始 JSON 未通过结构校验")
    meta = f'<p class="meta">{escape(" · ".join(summary))}</p>' if summary else ""
    response = displayed.get("dialogue") or "（本轮没有生成可展示的回复）"
    evidence = details("原始模型回复", observation.get("raw_reply"), raw=True)
    evidence += details("规范化输出", turn.get("normalized"))
    evidence += details("状态前后与规则事件", {"before": before, "after": after, "events": turn.get("events", [])})
    return (
        f'<section class="turn"><p class="round">第 {number} 轮</p><dl class="exchange">'
        f'<dt>玩家</dt><dd>{show(turn.get("player_input", ""))}</dd>'
        f"<dt>罗希</dt><dd>{show(response)}</dd></dl>{meta}{evidence}</section>"
    )


def render_case(row, case, anchor):
    status = row.get("status", "not_run")
    tone = "bad" if status in {"check_failed", "incomplete"} else "good" if status == "passed" else ""
    case_id = row["case_id"]
    title = case.get("title") or case_id
    case_id_label = f'<span class="case-id">{show(case_id)}</span>' if title != case_id else ""
    body = "".join(render_turn(turn, i) for i, turn in enumerate(row.get("turns") or [], 1))
    if row.get("missing_steps"):
        body += f'<p class="meta">未执行回合：{show("、".join(row["missing_steps"]))}</p>'
    if status == "not_run" and row.get("reason") == "requires_separate_runtime_or_browser_test":
        body += '<p class="meta">需另行执行网页或运行环境测试。</p>'
    body += render_checks(row.get("checks") or [])
    body += details("规则执行后的状态", row.get("final_state"))
    return (
        f'<article id="{anchor}"><div class="case-head"><h3>{case_id_label}{show(title)}</h3>'
        f'<span class="badge {tone}">{show(CASE_LABELS.get(status, status))}</span></div>{body}</article>'
    )


def write_report(run_dir, cases):
    rows = read_lines(run_dir / "results.jsonl")
    if not rows:
        raise ValueError("results.jsonl 中没有用例结果。")
    summary_path = run_dir / "summary.json"
    summary = json.loads(summary_path.read_text(encoding="utf-8-sig")) if summary_path.is_file() else {}
    by_id = {case["case_id"]: case for case in cases}
    counts = Counter(row.get("status", "not_run") for row in rows)
    metrics = [f'<span class="metric"><strong>{len(rows)}</strong>条记录</span>']
    for status in (*CASE_LABELS, *sorted(set(counts) - set(CASE_LABELS))):
        if counts[status]:
            metrics.append(f'<span class="metric"><strong>{counts[status]}</strong>{show(CASE_LABELS.get(status, status))}</span>')
    cards, issue_links = [], []
    # Keep original execution order and link directly to cases that need attention.
    for index, row in enumerate(rows, 1):
        anchor = f"case-{index}"
        case = by_id.get(row["case_id"], {})
        cards.append(render_case(row, case, anchor))
        if row.get("status") in {"check_failed", "incomplete"}:
            issue_links.append(f'<li><a href="#{anchor}">{show(row["case_id"])} {show(case.get("title", ""))}</a></li>')
    issues = f'<nav aria-label="待检查用例"><h2>优先查看</h2><ul>{"".join(issue_links)}</ul></nav>' if issue_links else ""
    meta = [run_dir.name]
    if summary.get("dataset_version"):
        meta.append(f"评测集 v{summary['dataset_version']}")
    if summary.get("model"):
        meta.append(f"模型 {summary['model']}")
    document = (
        '<!doctype html><html lang="zh-CN"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        f"<title>罗希评测结果</title><style>{STYLES}</style></head>"
        f'<body><header><div><h1>罗希评测结果</h1><p>{escape(" · ".join(meta))}</p></div></header>'
        f'<main><div class="metrics">{"".join(metrics)}</div>{issues}<h2>用例详情</h2>'
        f'{"".join(cards)}</main></body></html>\n'
    )
    path = run_dir / "report.html"
    path.write_text(document, encoding="utf-8")
    return path


def main():
    parser = argparse.ArgumentParser(description="将已有运行目录中的 results.jsonl 转成 report.html。")
    parser.add_argument("run_dir", type=Path, help="包含 results.jsonl 的运行目录")
    args = parser.parse_args()
    try:
        case_path = Path(__file__).resolve().parent / "dataset" / "cases.jsonl"
        cases = read_lines(case_path) if case_path.is_file() else []
        print(f"报告：{write_report(args.run_dir.resolve(), cases)}")
    except (OSError, ValueError) as exc:
        parser.exit(2, f"无法生成报告：{exc}\n")


if __name__ == "__main__":
    main()
