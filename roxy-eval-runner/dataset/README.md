# ROXY 产品评测集 v0.3

这版纳入了作者对三条评测问题的确认。共68条，包括44条角色对话、15条规则或记忆层受控测试和9条运行场景。全部已有判定要求或基线采集步骤；它们仍全部等待人工复核。运行场景需要后续执行器适配。

产品基线固定为 Moira7902/black-rain-roxy-agent 的提交 `a3627b7b80939c60725d2254544e4677d904aa6b`。产品源码不在本次工作中修改。所有题目自拟，借鉴公开benchmark的出题或评分方法，没有导入原始题目或官方样本分数。

## 文件

`cases.jsonl` 每行一个用例，是机器读取的完整记录。`profiles.json` 保存完整前置状态，避免把“低警惕”等自然语言当作运行配置。`rubrics.json` 是6份自拟的0至2分评分细则。`open_questions.json` 保存4项设计问题及其处理决定。`manifest.json` 记录版本、数量、来源文档与需求覆盖关系。`case_schema.json` 是单条用例的JSON Schema。`validation_report.json` 单列数据校验与离线规则核对结果。

## 审阅和执行

每条用例的must与must_not均为核心检查项，不能只运行checks就宣布该题通过。checks只描述可自动化的部分断言，phase分别指原始或处理中记录observation、规范化输出normalized，以及最终状态final。最终状态中的events指规则函数返回的事件列表，不是原始游戏状态字段。

profile_id选择前置快照。受控快照不等于经过真实对话自然达到该状态，多步用例须保留连续的实际输出和状态。独立用例每次重置。API调用失败、提前结局和评审失败均单独记录，不静默删除后续未完成步骤。

dialogue用例需要真实模型或网页执行器；deterministic用例使用operation内预设输出离线检查；runtime_scenario给出网页、故障注入或批次操作计划；pending_spec必须等blocked_by关联问题解决后启用。

所有记录review_status为draft，execution_status为not_run。离线规则核对单独报告预期与固定实现是否一致。真实模型和部署网页待实测。量表分数单独报告，不与状态正确性相加抵消。未测、不适用、待复核和失败须分开。

## 数据结构检查

在本目录运行 `python validate_dataset.py`。脚本使用Python标准库，不发网络请求。需要核对15条确定性预期时，可指定包含固定版本game_logic.py与memory_manager.py的目录：`python validate_dataset.py --product-dir /path/to/pinned/product`。产品版本必须由调用者核对，脚本不会自动下载或确认Git提交。

脚本逐项校验本JSON Schema用到的关键字；不宣称支持任意JSON Schema。checks是后续执行器的断言协议；脚本仅实现离线规则核对中用到的运算，不是完整的联网评测框架。

## 开发集与公开

当前全部样本为development，尚未建立独立留出集；不能把这批公开审阅过的样本称作盲测题。先用少量样本试标并复核评分分歧，再增加同类变式和独立测试数据。首批覆盖只表示15项需求各有代表题，不表示覆盖充分。

## 作者确认与基线

罗希具体流放原因和地下设施隐情未设定。允许含蓄回避，编造具体答案判错。重复出示同一张证件不能再次降低警惕。口头姓名可以记为玩家自述。Q004 仅采集性能基线，验收阈值留待实测。

RXY-R015 在固定提交离线复现了重复降警惕。初始55，第一次47，第二次预期47，实际39。规则不符写入报告，带 --product-dir 运行时退出码为1。对话和网页尚未实测。

## 方法来源

CharacterEval https://github.com/morecry/CharacterEval

CharacterBench https://github.com/thu-coai/CharacterBench

PersonaGym https://github.com/vsamuel2003/PersonaGym

每条 source.evidence 记录来源。产品路径相对固定提交。manifest.json 的 author_canon 记录作者补充的评测依据。针对补充设定的题以此作为验收预期。对固定产品版本实测时，应记录其提示词是否包含该设定。场景前情与临时资源是用例条件，游戏状态没有新增信任字段。两个前期需求与参考文档的稳定标识记录于manifest.json。
