from __future__ import annotations

import base64
import html
from pathlib import Path

import streamlit as st

from game_logic import (
    BAD_ENDING,
    GOOD_ENDING,
    QUEST_LABELS,
    apply_turn_rules,
    enforce_emotion,
    initial_game_state,
    suspicion_stage,
)
from memory_manager import add_long_term_memory, add_recent_turn
from npc_agent_core import safe_call_npc_agent

BASE_DIR = Path(__file__).resolve().parent
ASSET_DIR = BASE_DIR / "assets" / "roxy"

st.set_page_config(
    page_title="黑雨荒原｜罗希 NPC Agent Demo",
    page_icon="🌧️",
    layout="centered",
    initial_sidebar_state="expanded",
)

if "game_state" not in st.session_state:
    st.session_state.game_state = initial_game_state()
if "last_output" not in st.session_state:
    st.session_state.last_output = None
if "last_events" not in st.session_state:
    st.session_state.last_events = []
if "last_player_input" not in st.session_state:
    st.session_state.last_player_input = ""
if "last_error" not in st.session_state:
    st.session_state.last_error = ""


def image_data_uri(path: Path) -> str:
    encoded = base64.b64encode(path.read_bytes()).decode("utf-8")
    return f"data:image/png;base64,{encoded}"


def avatar_uri(emotion: str) -> str:
    path = ASSET_DIR / f"{emotion}.png"
    if not path.exists():
        path = ASSET_DIR / "calm.png"
    return image_data_uri(path)


def process_turn(player_text: str) -> None:
    player_text = (player_text or "").strip()
    if not player_text or st.session_state.game_state.get("ending"):
        return

    context_state = dict(st.session_state.game_state)
    context_state["suspicion_stage"] = suspicion_stage(context_state.get("suspicion", 55))
    output, error = safe_call_npc_agent(player_text, context_state)
    if error or output is None:
        st.session_state.last_error = error or "NPC输出失败。"
        return

    new_state, events = apply_turn_rules(player_text, output, st.session_state.game_state)
    output["emotion"] = enforce_emotion(output, new_state)

    if new_state.get("ending") == GOOD_ENDING:
        output["dialogue"] = "壁炉旁边还有块干地。只准一晚。你要是半夜发疯，我会先把你扔出去，再问你梦见了什么。"
        output["intent"] = "grant_stay"
        output["action_tag"] = "#把一条旧毯子丢到壁炉旁#"
    elif new_state.get("ending") == BAD_ENDING:
        if output.get("detected_action", {}).get("type") == "fire_weapon":
            output["dialogue"] = "枪机只发出一声潮湿的空响。罗希已经抓住你的手腕。下一秒，冷雨重新砸在脸上，酒馆的门在身后重重合拢。"
        else:
            output["dialogue"] = "出去。趁你还认得哪边是门。"
        output["intent"] = "expel"
        output["action_tag"] = "#拉开酒馆大门#"

    add_long_term_memory(new_state, output.get("memory_update", {}))
    add_recent_turn(new_state, player_text, output)

    st.session_state.game_state = new_state
    st.session_state.last_output = output
    st.session_state.last_events = events
    st.session_state.last_player_input = player_text
    st.session_state.last_error = ""


st.markdown(
    r'''
<style>
.stApp {
    background:
        linear-gradient(to bottom, rgba(6, 9, 14, .95), rgba(5, 8, 12, .99)),
        radial-gradient(circle at 50% 0%, rgba(76, 116, 148, .18), transparent 42%);
    color: #e6edf3;
}
.block-container { padding-top: 6rem !important; padding-bottom: 2rem; max-width: 920px;}
div[data-testid="stSidebar"] { background: rgba(8, 12, 18, .97); border-right: 1px solid rgba(110, 140, 165, .25); }
div[data-testid="stChatInput"] textarea { background: #0d141d !important; color: #eef6fb !important; border: 1px solid rgba(130, 165, 195, .4) !important; }
.rain-layer { position: fixed; inset: 0; pointer-events: none; z-index: 0; opacity: .12;
    background-image:
      linear-gradient(145deg, transparent 0 47%, rgba(165, 205, 235, .65) 47% 53%, transparent 53% 100%),
      linear-gradient(145deg, transparent 0 48%, rgba(155, 195, 225, .38) 48% 54%, transparent 54% 100%);
    background-size: 30px 48px, 52px 76px;
    background-position: 0 0, 18px 20px;
    animation: pixelRain .9s steps(8) infinite;
}
.rain-layer::before { content: ""; position: absolute; inset: 0; opacity: .45;
    background-image: linear-gradient(145deg, transparent 0 48%, rgba(190, 220, 245, .5) 48% 53%, transparent 53% 100%);
    background-size: 72px 98px; animation: pixelRainSlow 1.4s steps(9) infinite;
}
.scanline { position: fixed; inset: 0; pointer-events: none; z-index: 0; opacity: .04;
    background: repeating-linear-gradient(to bottom, rgba(255,255,255,.06) 0 1px, transparent 2px 4px); }
@keyframes pixelRain { from { background-position: 0 0, 18px 20px; } to { background-position: -32px 48px, -20px 96px; } }
@keyframes pixelRainSlow { from { background-position: 0 0; } to { background-position: -45px 98px; } }
.game-title { position: relative; z-index: 1; margin-top: 0.75rem; margin-bottom: 0.3rem; font-size: 2rem; font-weight: 800; color: #e6edf3; text-shadow: 0 0 18px rgba(130, 180, 220, 0.25)}
.subtitle { color: #8fa7ba; margin-bottom: 1rem; }
.scene-box, .dialogue-panel, .player-line, .ending-box { position: relative; z-index: 1; border: 2px solid #3d4d5d; background: rgba(13, 19, 28, .95); }
.scene-box { padding: 14px 16px; line-height: 1.85; margin-bottom: 16px; }
.scene-box::before { content: "荒原酒馆 / 黑雨夜"; display: block; color: #7f98ad; font-size: 12px; letter-spacing: .1em; margin-bottom: 7px; }
.player-line { border-left: 4px solid #8199ad; padding: 10px 12px; margin: 12px 0; color: #dbe6ef; }
.npc-grid { display: grid; grid-template-columns: 190px 1fr; gap: 16px; align-items: stretch; position: relative; z-index: 1; }
.avatar-frame { width: 100%; aspect-ratio: 1 / 1; border: 2px solid #526579; background: rgba(7, 11, 17, .95); display:flex; align-items:center; justify-content:center; overflow:hidden; }
.avatar-frame img { width: 100%; height: 100%; object-fit: cover; image-rendering: pixelated; }
.dialogue-panel { padding: 16px 18px; min-height: 190px; }
.npc-name { font-size: 19px; font-weight: 800; margin-bottom: 5px; }
.npc-meta { color: #8ba4b8; font-size: 13px; margin-bottom: 12px; }
.npc-line { font-size: 16px; line-height: 1.9; white-space: pre-wrap; }
.event-note { color: #9cb1c2; font-size: 13px; margin-top: 6px; }
.ending-box { padding: 18px; margin-top: 16px; border-color: #73899b; }
.todo-done { color: #9fc8ad; }
.todo-open { color: #a8b5c0; }
.item-desc { color: #9baebe; font-size: 13px; }
@media (max-width: 680px) { .npc-grid { grid-template-columns: 1fr; } .avatar-frame { width: 100%; max-width: 300px; justify-self: center; } }
</style>
<div class="rain-layer"></div><div class="scanline"></div>
''',
    unsafe_allow_html=True,
)

state = st.session_state.game_state

with st.sidebar:
    st.subheader("主线目标")
    for flag, label in QUEST_LABELS.items():
        done = bool(state["quest_flags"].get(flag))
        css = "todo-done" if done else "todo-open"
        mark = "■" if done else "□"
        st.markdown(f'<div class="{css}">{mark} {html.escape(label)}</div>', unsafe_allow_html=True)

    st.divider()
    st.subheader("罗希的警惕")
    suspicion = int(state.get("suspicion", 55))
    st.progress(suspicion / 100)
    st.write(f"**{suspicion}/100｜{suspicion_stage(suspicion)}**")

    st.divider()
    st.subheader("随身物品")
    inv = state["inventory"]
    for item_id in ["city_id", "lemon_candy", "wet_pistol"]:
        item = inv[item_id]
        status = "持有" if item.get("owned") else "已使用/已交出"
        with st.expander(f"{item['name']}｜{status}", expanded=False):
            st.markdown(f'<div class="item-desc">{html.escape(item["description"])}</div>', unsafe_allow_html=True)
            if item.get("owned") and not state.get("ending"):
                if item_id == "city_id" and st.button("出示证件", key="show_id", use_container_width=True):
                    process_turn("我把被雨水泡软的城市居民证递给罗希查看。")
                    st.rerun()
                elif item_id == "lemon_candy":
                    c1, c2 = st.columns(2)
                    if c1.button("吃掉", key="eat_candy", use_container_width=True):
                        process_turn("我拆开黏住的糖纸，把融化的柠檬糖吃掉。")
                        st.rerun()
                    if c2.button("递给罗希", key="offer_candy", use_container_width=True):
                        process_turn("我把那颗已经融化的柠檬糖递给罗希。")
                        st.rerun()
                elif item_id == "wet_pistol":
                    if st.button("坦白携带手枪", key="reveal_pistol", use_container_width=True):
                        process_turn("我告诉罗希，我身上有一把被雨泡坏的手枪，并慢慢把它拿出来。")
                        st.rerun()
                    if st.button("主动交出手枪", key="surrender_pistol", use_container_width=True):
                        process_turn("我把浸水的手枪握柄朝向罗希，主动交给她保管。")
                        st.rerun()

    st.divider()
    with st.expander("调试：记忆与状态"):
        st.write("最近完整对话：", len(state.get("recent_history", [])))
        st.write("长期记忆：", len(state.get("long_term_memories", [])))
        st.json(state, expanded=False)

    if st.button("重新开始", use_container_width=True):
        st.session_state.game_state = initial_game_state()
        st.session_state.last_output = None
        st.session_state.last_events = []
        st.session_state.last_player_input = ""
        st.session_state.last_error = ""
        st.rerun()

st.markdown('<div class="game-title">黑雨荒原</div>', unsafe_allow_html=True)
st.markdown('<div class="subtitle">罗希 NPC Agent Demo｜活过今晚，比知道真相更重要。</div>', unsafe_allow_html=True)
st.markdown(
    '''
<div class="scene-box">
黑雨敲打着酒馆的旧窗。你浑身湿透，鞋底沾满荒原的泥。柜台后的长耳精灵抬起金色眼睛，没有欢迎，也没有立刻赶你出去。
</div>
''',
    unsafe_allow_html=True,
)

if not state.get("ending"):
    player_input = st.chat_input("输入你想对罗希说的话……")
    if player_input:
        with st.spinner("罗希正在判断你究竟是流放者，还是黑雨送来的麻烦……"):
            process_turn(player_input)
        st.rerun()

if st.session_state.last_error:
    st.error(st.session_state.last_error)

output = st.session_state.last_output
if output:
    player_text = html.escape(st.session_state.last_player_input)
    emotion = output.get("emotion", "calm")
    avatar = avatar_uri(emotion)
    dialogue = html.escape(output.get("dialogue", ""))
    action_tag = html.escape(output.get("action_tag", ""))
    intent = html.escape(output.get("intent", "answer"))
    st.markdown(f'<div class="player-line">你：{player_text}</div>', unsafe_allow_html=True)
    st.markdown(
        f'''
<div class="npc-grid">
  <div class="avatar-frame"><img src="{avatar}" alt="罗希 {emotion} 表情"></div>
  <div class="dialogue-panel">
    <div class="npc-name">罗希</div>
    <div class="npc-meta">emotion: {emotion}　intent: {intent}　{action_tag}</div>
    <div class="npc-line">{dialogue}</div>
  </div>
</div>
''',
        unsafe_allow_html=True,
    )
    for event in st.session_state.last_events:
        st.markdown(f'<div class="event-note">• {html.escape(event)}</div>', unsafe_allow_html=True)
    with st.expander("查看本轮结构化输出", expanded=False):
        st.json(output, expanded=True)
else:
    st.info("你可以先问这里是什么地方，也可以说明自己为何来到这里。证件和其他物品可以在侧边栏使用。")

if state.get("ending") == GOOD_ENDING:
    st.markdown(
        '''<div class="ending-box"><b>【结局：雨夜暂歇】</b><br><br>你获得了在废弃酒馆停留一夜的许可。黑雨仍在窗外落下，但至少今晚，门没有在你面前关上。</div>''',
        unsafe_allow_html=True,
    )
elif state.get("ending") == BAD_ENDING:
    st.markdown(
        '''<div class="ending-box"><b>【坏结局：拒之门外】</b><br><br>酒馆的灯隔着雨幕迅速变远。荒原重新接纳了你——如果那也能算接纳。</div>''',
        unsafe_allow_html=True,
    )

with st.expander("最近对话记录", expanded=False):
    for turn in state.get("recent_history", []):
        st.markdown(f"**你：** {turn['player']}")
        st.markdown(f"**罗希：** {turn['npc']}")
        st.caption(f"emotion={turn['emotion']} | intent={turn['intent']} | {turn['action_tag']}")
        st.divider()
