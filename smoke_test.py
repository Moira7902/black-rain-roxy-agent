from game_logic import apply_turn_rules, initial_game_state
from memory_manager import add_long_term_memory, add_recent_turn

state = initial_game_state()
mock = {
    "emotion": "talk",
    "dialogue": "这里以前是酒馆。现在只剩下能挡雨这一项用途。",
    "intent": "answer",
    "action_tag": "#看了一眼窗外#",
    "risk_tags": [],
    "positive_tags": ["calm_and_coherent"],
    "quest_candidates": ["asked_about_tavern"],
    "detected_action": {"type": "ask_tavern", "item_id": "none", "target": "酒馆"},
    "memory_update": {"should_write": False, "memory_type": "none", "content": "", "importance": 0},
}
state, events = apply_turn_rules("这里是什么地方？", mock, state)
add_long_term_memory(state, mock["memory_update"])
add_recent_turn(state, "这里是什么地方？", mock)
assert state["quest_flags"]["asked_about_tavern"] is True
assert len(state["recent_history"]) == 1
print("smoke test passed", events)
