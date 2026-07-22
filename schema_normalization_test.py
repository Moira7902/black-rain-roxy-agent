import os
import sys
import types

os.environ.setdefault("DEEPSEEK_API_KEY", "test-key")

fake_openai = types.ModuleType("openai")
class FakeOpenAI:
    def __init__(self, *args, **kwargs):
        pass
fake_openai.OpenAI = FakeOpenAI
sys.modules["openai"] = fake_openai

from npc_agent_core import NPCOutput, normalize_npc_output

raw = {
    "speaker": "罗希",
    "emotion": "平静",
    "dialogue": "进来。门关上，别把雨带得到处都是。",
    "intent": "允许玩家进入并提醒关门",
    "action_tag": "#侧身让开门口#",
    "risk_tags": [],
    "positive_tags": ["正常交流"],
    "quest_candidates": [],
    "detected_action": "greeting",
    "memory_update": "玩家进入酒馆，罗希首次回应。",
    "rule_notes": "普通开场。"
}

normalized = normalize_npc_output(raw)
parsed = NPCOutput.model_validate(normalized)
assert parsed.intent == "warn"
assert parsed.detected_action.type == "none"
assert parsed.memory_update.should_write is False
assert parsed.emotion == "calm"
print("schema normalization test passed")
