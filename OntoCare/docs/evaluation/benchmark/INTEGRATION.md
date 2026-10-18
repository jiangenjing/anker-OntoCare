# 红蓝对抗评测集成

现有数据、用例编号与历史结果继续复用。没有虚构 T5-02、T4-03 编号，也没有复制出另一套可能失同步的数据。

```text
benchmark/
├── main.py                         独立进程入口
├── api.py                          本机启动、状态与 Trace API
├── agents/
│   ├── red_team.py                  Persona 首封原文、模型/脚本追问、状态保护
│   ├── blue_team.py                 调用实际 /api/chat/stream，不是模拟客服
│   ├── judge.py                     每轮规则检查、可选模型评分
│   └── model.py                     红队/裁判专用模型请求，记录调用状态
├── config/prompts.py                三个职责的 System Prompt 与版本
├── orchestrator/
│   ├── runner.py                    编排、终止、Trace 与新结果落盘
│   └── chaos.py                     只在蓝队调用范围内注入故障
├── ontocare-persona-vectors.json     8 个 Persona，first_message 来自真实源表
├── ontocare-user-test-cases.json     复用现有核心与补充用例
├── ontocare-adversarial-tests.json   10 个固定攻击用例，不冒充真实来信
├── ontocare-benchmark-runner.py      保留历史基准与终态断言的原运行器
└── output/<run_id>/                 运行时生成；不打包用户临时任务
    ├── request.json
    ├── benchmark_results.json
    ├── traces/<case_id>-<repeat>.json
    └── worker.log
```

## 实际分工

- 新动态路径对应 U093–U100：首轮逐字来自 P01–P08 工单，后续可用 LLM 生成；事实标识、语言字段与状态增量由代码检查。模型检查不是完整事实证明，生成内容保留供裁判复核。
- 其余固定用例继续走原运行器，包括 74 个核心任务、边界、10 个攻击和混沌矩阵。攻击只在固定对抗用例中运行；没有给真实 Persona 伪造“恶意客户”身份。
- 蓝队直接调用真实客服应用，附加蓝队 Prompt 保留原 JSON 格式与规则权限；同一 worker 中串行执行，生产演示会话不被清空。
- 新动态裁判逐轮检查并按需请求语义模型；历史轨迹未测逐轮分数的位置显示“未测”。整段历史裁判分数独立显示。
- `goal_achieved` 是模型语义估计，只有本轮硬断言通过且动作合法才可终止；不代表发生退款。安全停止表示“建议安全核查”，不是已经接通专员。没有终态金标准的项目为 null。
- 情绪上限 10；受耐心与 max_turns 双重限制，最多 8 轮。模型异常显示 ERROR/UNAVAILABLE，使用本语言固定追问或待人工复核，不伪装成模型成功。

## API

启动：`POST /api/benchmark/run`，返回 HTTP 202 与 run_id/status_url。采用异步方式，避免模型调用把网页请求长时间阻塞。

```json
{"case_ids":["U093"],"mode":"online","red_mode":"llm","max_turns":3,"repeats":1,"judge":true,"fault":null}
```

- mode：offline / online；离线必须 red_mode=scripted、judge=false。
- max_turns：1–8；repeats：1、3、8。未完整重复的 pass³/pass⁸ 为 null。
- fault：null、timeout、rate_limit、partial_response、schema_drift。新动态超时探针等待 0.05 秒后抛出，只验证错误处理；不能拿它测超时时延。历史矩阵仍使用原 5.05 秒探针。
- 固定用例保留原脚本轮数和断言，max_turns 仅作用于动态 Persona。配置故障也必须实际命中，缓存绕过依赖不能算故障容错通过。
- `GET /api/benchmark/runs/<run_id>` 查询 RUNNING/COMPLETED/FAILED/INTERRUPTED 及已保存结果。
- `GET /api/benchmark/trace/U093?run_id=<run_id>&repeat=1` 获取本次逐轮时间轴。
- 不传 run_id 时，返回最近已归档修复结果，找不到再读取原历史结果，并标注结果文件来源。
- 同时只接受一项本进程启动的任务；模型密钥从服务端环境读取，既不写入请求文件也不发给浏览器。接口限制本机且拒绝跨站 Origin。这不是生产权限系统。

命令行：将同一 JSON 写到 request.json，然后执行：

```sh
.venv/bin/python benchmark/main.py --request request.json --output benchmark/output/manual-run
```

历史全矩阵命令继续有效，勿覆盖已冻结的结果文件。

## 页面

`/benchmark.html#view=principles`：查看架构、Prompt 要点、混沌工程和“运行 P01 小样本”。“回放流程”只是动画；“运行小样本”会真正启动任务。在线小样本会消费已配置的模型服务额度。

新结果按钮打开真实红队输入、蓝队响应与 Trace、逐轮裁判结果。所有用例仍可查看原始 Excel 行与原文。

“标记已修复”只保存本浏览器的待复测备注，按结果版本/运行编号隔离，不改变 PASS/FAIL 或历史日志。

`static/benchmark-principles.html` 是无外部脚本单文件。双击打开可查看内嵌历史证据；启动后端评测必须使用本机服务页面。新增运行不自动混入旧 pass^k 图表，防止不同版本、不同生成方式混算。

## 与附件示例的必要修正

不能把“已为您转接”“已升级专员”当默认兜底，也不能把任意未出现的订单号一律判幻觉——回答“Anker999 未找到”是合法澄清。没有根据的退款、换新资格不能从示例 Prompt 注入。无真实交易执行器时只验证规则/案件终态；不虚构退款数据库结果或总分 92。
