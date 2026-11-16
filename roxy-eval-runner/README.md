# 罗希自动评测脚本 v0.3

随包附带 v0.3 评测数据。脚本分两步使用。先跑程序规则，再采集真实对话的回复和状态。对话证据可以交给人或 LLM 裁判。

## 准备项目

使用 Python 3.10 或更新版本。解压后进入本目录，将下面的路径换成罗希项目在你电脑上的目录。规则测试使用 Python 标准库。Windows 下如果使用 Python 启动器，把命令开头的 `python` 换成 `py -3`。

```sh
python run_eval.py --product-dir "/你的路径/black-rain-roxy-agent" --suite rules
```

脚本默认测试本地版本，报告会记录所用文件的指纹、能读取到的 Git 提交及与基线的差异。指纹忽略系统换行格式和文件末尾的空行。需要复现固定版本时，可以用 [罗希项目基线提交](https://github.com/Moira7902/black-rain-roxy-agent/tree/a3627b7b80939c60725d2254544e4677d904aa6b) 并加上 `--strict-baseline`。

固定版本的预期记录为 14 条通过，1 条失败。RXY-R015 复现同一张证件第二次核验时又减了 8 点警惕。脚本仍会保存本次完整结果，退出码为 1。想单独复现，可把 `--suite rules` 换成 `--case RXY-R015`。

## 采集第一批对话

在运行脚本的 Python 环境里安装罗希项目的 `requirements.txt`。沿用项目现有的 `DEEPSEEK_API_KEY` 配置，可以设在本地环境变量或项目自己的 `.env` 中。`DEEPSEEK_MODEL` 如有配置也会沿用。先单跑一道确认连接，再跑试评批次。

```sh
python run_eval.py --product-dir "/你的路径/black-rain-roxy-agent" --case RXY-D002 --live
python run_eval.py --product-dir "/你的路径/black-rain-roxy-agent" --suite pilot --live
```

试评批次有 12 道用例，全部走完共 16 个回合。选择涵盖黑雨问答、否定语义、交枪、留宿、状态注入、输出结构、记忆、握手、身份和披露边界。真实模型调用需要 `--live`。校准裁判后，换成 `--suite dialogue --live` 可采集 44 条对话题。也可以重复写 `--case` 选择个别题目。

## 看结果

每次运行生成一个新的 `runs/` 子目录。`--out` 可以指定新的输出目录。双击 `report.html`，即可在浏览器里逐条看结果。

| 文件 | 内容 |
| --- | --- |
| `report.html` | 用例状态、玩家输入与罗希回复、预期与实际。原始输出和状态明细可以按需展开。 |
| `results.jsonl` | 每题一条记录。包含自动断言、模型原文、规范化结果、实际台词、状态前后和规则事件。 |
| `judge_inputs.jsonl` | 已走完的对话及对应评分维度。即使自动检查失败，也可继续评分。未完成用例的证据保留在结果文件。 |
| `summary.json` | 运行的用例、数据与产品版本、被测模型和各类状态的数量。 |

对已经跑完的结果，在新版脚本所在目录打开 PowerShell，把下面的路径换成旧运行目录，即包含 `results.jsonl` 的那一层。转换只读取已有结果，不调用模型。

```powershell
py -3 .\render_report.py "D:\你的路径\旧脚本\runs\运行编号"
```

将 `judge_prompt.txt` 作为裁判指令，将 `judge_inputs.jsonl` 每行作为一个待判用例。先用相同回复比对人工和裁判评分。维度分数、核心条件、程序断言分别保留。`ready_for_review` 表示执行完成并等待评审。`check_failed` 和 `incomplete` 会令本次运行退出码为 1。

脚本复用项目原有的模型请求、规范化和回合结算函数。计时只覆盖模型调用和本地回合处理。9 条网页、并发及其他运行场景需要另行执行。`--suite all --live` 会把这些场景明确记为 `not_run`。裁判调用留在独立阶段，当前脚本只准备判分输入。
