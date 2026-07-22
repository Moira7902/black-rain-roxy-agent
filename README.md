# 黑雨荒原：罗希 NPC Agent Demo

这是一个面向 **AI 游戏叙事 / 智能 NPC / Agent 评测** 作品集的 Streamlit Demo。

## 已实现

- 末世 + 西幻 + 认知污染的具体世界观
- 罗希的知识边界、语言风格与信息披露规则
- 最近 12 轮完整对话上下文
- 最多 30 条长期精简记忆
- 警惕阶段与坏结局差分
- TODO 主线目标与确定性任务 Flag
- DeepSeek 结构化 JSON 输出 + 本地字段规范化 + Pydantic 严格校验
- 模型负责语义识别与角色表演，程序负责字段兜底、警惕、任务、物品和结局


## 推荐试玩顺序

1. 询问这是什么地方或酒馆规矩。
2. 说明自己刚被城市流放，淋着黑雨找到了这里。
3. 从侧边栏出示居民证。
4. 保持理智、坦诚交流，让警惕降到 30 以下。
5. 请求在酒馆过夜。

也可尝试超游发言、编造物品、威胁罗希或使用手枪，观察警惕变化和坏结局。

## 记忆设计

- `recent_history`：保留最近 12 轮玩家与罗希的完整对话，用于代词、追问和语气衔接。
- `long_term_memories`：保存最多 30 条重要事实摘要，用于窗口外的角色记忆。
- `quest_flags / inventory / suspicion`：确定性游戏状态，非自然语言记忆，避免模型随意改写。

## 文件说明

- `app.py`：Streamlit 前端和会话流程
- `npc_agent_core.py`：DeepSeek 调用、Prompt、结构化输出校验
- `game_logic.py`：警惕、任务、物品、结局等确定性规则
- `memory_manager.py`：短期完整上下文与长期记忆
- `data/world_lore.json`：世界观
- `data/roxy_profile.json`：罗希角色设定
- `assets/roxy/`：表情头像

## 素材备注

头像素材来自51gameart.com。
