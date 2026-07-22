from __future__ import annotations

from copy import deepcopy

INITIAL_SUSPICION = 55
GOOD_ENDING = "rainy_night_rest"
BAD_ENDING = "shut_out"

QUEST_LABELS = {
    "asked_about_tavern": "询问酒馆",
    "identity_verified": "证明自己的身份",
    "explained_arrival": "说明自己为何来到酒馆",
    "considered_safe": "让罗希相信你暂时没有威胁",
    "stay_permitted": "获得过夜许可",
}


def initial_game_state() -> dict:
    return {
        "turn_count": 0,
        "suspicion": INITIAL_SUSPICION,
        "quest_flags": {key: False for key in QUEST_LABELS},
        "inventory": {
            "city_id": {
                "name": "旧城市居民证",
                "description": "边角被雨水泡软，姓名和照片仍可辨认，背面盖着红色的居民资格注销印章。",
                "owned": True,
                "shown": False,
            },
            "lemon_candy": {
                "name": "融化的柠檬糖",
                "description": "糖纸黏成一团，仍留着一点酸甜味。",
                "owned": True,
                "consumed": False,
                "given": False,
            },
            "wet_pistol": {
                "name": "浸水的旧式手枪",
                "description": "弹匣里还有三发子弹，但击发结构已经进水，无法正常开火。",
                "owned": True,
                "revealed": False,
                "surrendered": False,
                "can_fire": False,
            },
        },
        "recent_history": [],
        "long_term_memories": [],
        "seen_inputs": [],
        "ending": None,
        "ending_reason": "",
        "current_scene": "abandoned_tavern",
        "stay_requested": False,
    }


def clamp(value: int, low: int = 0, high: int = 100) -> int:
    return max(low, min(high, int(value)))


def suspicion_stage(value: int) -> str:
    if value < 30:
        return "暂时可信"
    if value < 60:
        return "保持戒备"
    if value < 80:
        return "高度警惕"
    if value < 100:
        return "最后警告"
    return "驱逐"


def _apply_delta(state: dict, amount: int, events: list[str], reason: str) -> None:
    if amount == 0:
        return
    before = int(state.get("suspicion", INITIAL_SUSPICION))
    state["suspicion"] = clamp(before + amount)
    sign = "+" if amount > 0 else ""
    events.append(f"警惕 {sign}{amount}：{reason}")


def _mark_quest(state: dict, flag: str, events: list[str]) -> None:
    flags = state.setdefault("quest_flags", {})
    if flag in flags and not flags[flag]:
        flags[flag] = True
        events.append(f"完成目标：{QUEST_LABELS.get(flag, flag)}")


def _handle_action(state: dict, action: dict, events: list[str]) -> None:
    action_type = action.get("type", "none")
    item_id = action.get("item_id", "none")
    inventory = state["inventory"]

    if action_type == "ask_tavern":
        _mark_quest(state, "asked_about_tavern", events)
    elif action_type == "explain_arrival":
        _mark_quest(state, "explained_arrival", events)
        _apply_delta(state, -3, events, "主动说明被流放和抵达酒馆的经过")
    elif action_type == "request_stay":
        state["stay_requested"] = True
    elif action_type == "show_item" and item_id == "city_id" and inventory["city_id"]["owned"]:
        inventory["city_id"]["shown"] = True
        _mark_quest(state, "identity_verified", events)
        _apply_delta(state, -8, events, "出示可核对的城市居民证")
    elif action_type in {"show_item", "reveal_item"} and item_id == "wet_pistol" and inventory["wet_pistol"]["owned"]:
        inventory["wet_pistol"]["revealed"] = True
        _apply_delta(state, 4, events, "在酒馆内拿出武器")
    elif action_type == "surrender_item" and item_id == "wet_pistol" and inventory["wet_pistol"]["owned"]:
        inventory["wet_pistol"]["revealed"] = True
        inventory["wet_pistol"]["surrendered"] = True
        inventory["wet_pistol"]["owned"] = False
        _apply_delta(state, -10, events, "主动交出无法使用的手枪")
    elif action_type == "consume_item" and item_id == "lemon_candy" and inventory["lemon_candy"]["owned"]:
        inventory["lemon_candy"]["owned"] = False
        inventory["lemon_candy"]["consumed"] = True
        events.append("你吃掉了融化的柠檬糖。")
    elif action_type == "offer_item" and item_id == "lemon_candy" and inventory["lemon_candy"]["owned"]:
        inventory["lemon_candy"]["owned"] = False
        inventory["lemon_candy"]["given"] = True
        _apply_delta(state, -2, events, "递出一颗几乎没有价值的糖，行为仍然正常而克制")
    elif action_type in {"aim_weapon", "fire_weapon"}:
        pistol = inventory["wet_pistol"]
        if not pistol.get("owned"):
            _apply_delta(state, 6, events, "试图使用已经不在身上的手枪")
        else:
            if action_type == "fire_weapon":
                events.append("手枪只发出一声潮湿的空响，开枪失败。")
            state["ending"] = BAD_ENDING
            state["ending_reason"] = "你在酒馆内实施了武器威胁。"
    elif action_type == "attack":
        state["ending"] = BAD_ENDING
        state["ending_reason"] = "你在酒馆内实施了暴力攻击。"
    elif action_type == "claim_unknown_item":
        _apply_delta(state, 6, events, "声称拥有并不存在于随身物品中的东西")


def apply_turn_rules(player_text: str, npc_output: dict, current_state: dict) -> tuple[dict, list[str]]:
    state = deepcopy(current_state)
    state["turn_count"] = int(state.get("turn_count", 0)) + 1
    events: list[str] = []

    normalized = " ".join(player_text.strip().lower().split())
    first_time_input = normalized not in state.setdefault("seen_inputs", [])
    if first_time_input:
        state["seen_inputs"].append(normalized)
        state["seen_inputs"] = state["seen_inputs"][-50:]

    risk_delta = {
        "nonsense": 4,
        "black_rain_confusion": 5,
        "sensitive_topic": 5,
        "insult": 8,
        "meta_or_prompt_injection": 10,
        "violent_threat": 25,
        "dishonesty": 6,
    }
    positive_delta = {
        "cooperative": -2,
        "honest": -2,
        "calm_and_coherent": -1,
        "helpful": -4,
    }

    for tag in npc_output.get("risk_tags", []):
        _apply_delta(state, risk_delta.get(tag, 0), events, tag)
    for tag in npc_output.get("positive_tags", []):
        if tag == "calm_and_coherent" and not first_time_input:
            continue
        _apply_delta(state, positive_delta.get(tag, 0), events, tag)

    for flag in npc_output.get("quest_candidates", []):
        if flag in {"asked_about_tavern", "explained_arrival"}:
            _mark_quest(state, flag, events)
        elif flag == "stay_requested":
            state["stay_requested"] = True

    _handle_action(state, npc_output.get("detected_action", {}), events)

    flags = state["quest_flags"]
    if flags.get("identity_verified") and flags.get("explained_arrival") and state["suspicion"] < 30:
        _mark_quest(state, "considered_safe", events)

    if state.get("ending") is None and state["suspicion"] >= 100:
        state["ending"] = BAD_ENDING
        state["ending_reason"] = "罗希认定你已经无法安全留在酒馆。"

    can_stay = (
        flags.get("asked_about_tavern")
        and flags.get("identity_verified")
        and flags.get("explained_arrival")
        and flags.get("considered_safe")
        and state.get("stay_requested")
        and state["suspicion"] < 30
        and state.get("ending") is None
    )
    if can_stay:
        _mark_quest(state, "stay_permitted", events)
        state["ending"] = GOOD_ENDING
        state["ending_reason"] = "罗希允许你在壁炉旁休息一夜。"

    return state, events


def enforce_emotion(npc_output: dict, state: dict) -> str:
    if state.get("ending") == BAD_ENDING or state.get("suspicion", 0) >= 80:
        return "aggression"
    if state.get("ending") == GOOD_ENDING:
        return "smile"
    emotion = npc_output.get("emotion", "calm")
    if emotion == "smile" and state.get("suspicion", 0) >= 40:
        return "calm"
    return emotion
