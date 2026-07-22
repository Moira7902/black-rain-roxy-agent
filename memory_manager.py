from __future__ import annotations

from copy import deepcopy

RECENT_TURN_LIMIT = 12
LONG_TERM_MEMORY_LIMIT = 30


def normalize_memory(text: str) -> str:
    return " ".join((text or "").strip().split()).lower()


def add_long_term_memory(state: dict, memory: dict) -> None:
    if not memory or not memory.get("should_write"):
        return
    content = (memory.get("content") or "").strip()
    if not content:
        return

    record = {
        "type": memory.get("memory_type", "event"),
        "content": content,
        "importance": int(memory.get("importance", 1)),
        "source_turn": int(state.get("turn_count", 0)),
    }
    key = normalize_memory(content)
    existing = state.setdefault("long_term_memories", [])
    for item in existing:
        if normalize_memory(item.get("content", "")) == key:
            item["importance"] = max(int(item.get("importance", 1)), record["importance"])
            item["source_turn"] = record["source_turn"]
            return

    existing.append(record)
    existing.sort(key=lambda x: (int(x.get("importance", 1)), int(x.get("source_turn", 0))), reverse=True)
    del existing[LONG_TERM_MEMORY_LIMIT:]


def add_recent_turn(state: dict, player_text: str, npc_output: dict) -> None:
    history = state.setdefault("recent_history", [])
    history.append({
        "turn": int(state.get("turn_count", 0)),
        "player": player_text,
        "npc": npc_output.get("dialogue", ""),
        "emotion": npc_output.get("emotion", "calm"),
        "intent": npc_output.get("intent", "answer"),
        "action_tag": npc_output.get("action_tag", ""),
    })
    if len(history) > RECENT_TURN_LIMIT:
        del history[:-RECENT_TURN_LIMIT]


def context_snapshot(state: dict) -> dict:
    return {
        "recent_history": deepcopy(state.get("recent_history", [])),
        "long_term_memories": deepcopy(state.get("long_term_memories", [])),
    }
