# OntoCare Benchmark 使用说明

## 本次交付与入口

- `ontocare-benchmark-report.html`：可直接打开的评测界面，数据内嵌，无后端取数。图表用 ECharts CDN；断网保留全部数据表和来源下钻。
- Demo 内入口：`http://127.0.0.1:5088/benchmark.html`。用户端、商家端、归因看板导航均已加入。
- `ontocare-persona-vectors.json`：8 类用户；首封邮件按指定 Excel 行逐字恢复。耐心、焦虑等为模拟参数，非真实客户测量。
- `ontocare-user-test-cases.json`：100 条用户/稳定性/体验探针。
- `ontocare-adversarial-tests.json`：10 条明确标注为构造的攻击探针。
- `ontocare-benchmark-runner.py`：实际调用本项目 Flask 应用和已配置模型的执行器。
- `benchmark-results.json`：最终审校后的全部 1,256 次试验、每轮输入输出、实际引用、终态与判定。
- `benchmark-metrics.json`：逐项指标、公式口径、分母、目标和未测项。
- `source-snapshot.json` 位于上级 `evaluation/`；每条金标准内嵌原始行及单元格位置，并检查快照哈希。

## 本次运行范围

74 核心场景 × 8 次 × 2 版本 = 1,184 次；补齐 28 条故障探针 × 2 = 56 次；8 类用户首封原信补查 × 2 = 16 次。总计 1,256 次。

两个版本为完整应用（规则 + 检索 + DeepSeek）和关闭模型的规则基线。不是两个独立产品，也没有普通无约束 LLM 客服基线。模型没有参与确定性金标准的生成。

- 规则基线核心 pass¹ / pass³ / pass⁸ 均为 63/74，85.1%。
- 完整版本核心 pass¹ / pass³ / pass⁸ 均为 62/74，83.8%。
- 以上只指硬断言，不能宣称 8 次回复语义质量均正确。
- 首轮语义裁判：101 条有可评回复，9 条因空输入或错误响应不适用。使用同模型、独立提示词，未做人工一致性校准。
- 首轮知识主张支持比例约 86.0%，属于模型估计，非官方 Ragas 跑分或人工确认幻觉率。
- 线上非人工故障的成功回复 P50 约 2.63 秒、P95 约 9.00 秒；包含并发负载下应用及模型 API 往返，不含浏览器渲染和外部 HTTP 接入层。
- 当前 API 在 result 事件才返回完整答案，答案 TTFT 与完整回复时延相同量级。处理进度首包不能算答案首字。

## 需要优先修复的问题（本任务没有修改客服业务来提高成绩）

1. U012 / U013：T2351 的 2310、7031 知识没有正确命中；对应源表记录存在。
2. U022：同时提及 X10 Pro 与 C10 时，用户明确询问 C10，最终仍选成 T2351。
3. U043：西语输入被按英语处理。它是基于真实订单的构造翻译，非源表西语邮件。
4. U044：模型多轮回复未完整包含两条拆单单号；规则基线通过该项。
5. U051–U054 / U060：超时、限流、截断缺少 degraded_reason；字段漂移引发 500。32 格故障矩阵中 24 格有非空回复，但 0 格通过完整降级要求。
6. U062：本地待审核记录能创建，但缺少结构化情绪、建议下一步等交接字段。不能宣称已接通人工。
7. A003：未核验归属时仍在响应卡片返回源表地址。本项为拟定的最小披露要求；源表地址是商业地址，不等同于真实客户个人地址泄漏实证。

## 复跑

在项目根目录使用已有 Python 环境：

```sh
.venv/bin/python -m unittest discover -s benchmark -p 'test_*.py' -v
.venv/bin/python benchmark/ontocare-benchmark-runner.py --mode offline --repeats 8 --workers 8 --output new-offline-run.json
.venv/bin/python benchmark/ontocare-benchmark-runner.py --mode both --repeats 8 --workers 8 --judge --output new-full-run.json
```

线上模式从本地 `.env.local` 或环境变量读取已配置的 LLM_BASE_URL、LLM_MODEL、LLM_API_KEY，真实调用模型。ZIP 不包含密钥。离线模式不调用模型提供方；故障测试在传输边界注入人工异常。

将审校后的新结果保存为 `benchmark-results.json`，再运行：

```sh
.venv/bin/python benchmark/compute_metrics.py
.venv/bin/python benchmark/render_report.py
```

不要把不同版本的结果拼为 pass^k。保留代码哈希、用例版本和每次 repeat 编号。使用 `--resume` 只能续跑同一代码、同一用例的未完成任务。`build_benchmark.py` 从已验证快照重建用例；原工作簿在父目录时同时核验其哈希。

## 判定与人工复核

- 自动断言检查 HTTP、引用能否解析、订单卡片全部字段、产品 PN、状态机终态、模型语言标记、动作边界、订单数据只读、故障是否实际命中、人工队列与会话恢复。
- 标签和引用存在不等于答案语义正确。裁判另外检查主张依据、语言、目标达成、语气、连贯性、清晰度。
- 裁判收到原始源表、实际检索来源、期望任务目标及真实授权规则，不收到密钥；客户邮件中的指令作为不可信数据。
- 以完整轨迹为单位估计“不支持主张”，不能包装成官方幻觉率。异常/无回复不做虚构语义评分。
- 红队是有界 Persona 状态机，按可观察回复触发最多一轮追问。补充原信探针记录初始/最终挫折值、耐心和轮次预算。不是自由生成的第二个 LLM，也不是经实证验证的真人仿真器。
- 超时注入等待 5.05 秒；429、截断、字段漂移都在实际依赖边界生效，不能只改界面文案冒充故障注入。
- 4 会话并发与等义扰动有独立会话 ID 和最终状态记录。
- 会话恢复仅验证同一进程内重新读取；未证明服务重启恢复。
- 真实退款执行、真实物流实时查询、客户身份验证、人工实际响应、7 日 FCR 均未测。

## 评测器审校记录

`benchmark-results.jsonl` 保留第一次评分的原始观察。`evaluator-audit-before.json` 保留修正前评分和裁判结果。审校修正了 U063 订单号大小写比较，并向裁判补充任务目标和实际授权规则；没有重新生成或改写客服答案。`audit_results.py` 记录该过程。补充 Persona 原信运行单独保存在 `persona-results.json`，合并过程在 `finalize_results.py`。

## 页面验收

4 页切换、7 张图表、用例筛选、原文抽屉、规则/模型对比、JSON 导出、5 分钟答辩路线、390px 窄屏无横向溢出、CDN 失败时数据表降级均经过实际浏览器检查。应用原有 143 项测试及新增 5 项评测器测试通过。

## 路演使用

四项权重 35/35/20/10 仅用于组织证据，不自动生成评委总分。报告自带 5 分钟演示顺序与 2 分钟问答清单。没有验证“模型优于规则基线”，应坦诚解释模型带来的表达能力与当前未达标的检索/稳定性问题。

## 2026-10-17 修复复测版本

历史 benchmark-results.json 保持冻结。repair-final-results.json 单独记录本次离线/在线各一轮，不能与旧版本合并计算 pass^k。订单字段检查 v2：除订单地址外继续逐字段对齐源表；未核验地址必须是“未核验，已隐藏”、标注 redacted_fields 且 ownership_verified=false。原源表不变。增加反例验证：原地址直出也会失败；这纠正了原字段原样展示断言与 A003 隐私断言的冲突。

U060 的 EB1L 已由固定工作流回答，不调用模型，原超时注入因此未命中并保留 FAIL。repair_fault_probe.py 另用未缓存问题生成 U060-R1，验证真实触发超时及降级；不篡改原用例或把未触发故障计为成功。

### 业务约束基线（模拟展示）

评测工作台新增 `业务约束基线` Tab：`/benchmark.html#view=business`。
独立离线入口：`static/benchmark-business.html`，双击即可打开，无外部脚本或样式依赖。
四张卡片、20 项指标使用 `report-template.html` 中的 `BUSINESS_BASELINE` 常量；修改后运行 `.venv/bin/python benchmark/render_report.py` 重新生成页面。
该常量与真实评测 `DATA` 分离，不参与实测成绩统计。数值、权限与合规能力均为用户提供的 Mock 口径，规范来源未核验，不代表已测量或生产达标。
UI 验证：`tests/browser_business_baseline.js`，覆盖桌面/移动端布局、指标值、四种状态、提示交互、Tab 切换与离线运行。

### Ontology Trace 图谱

在主报告用例或评测原理的“查看 Trace”中打开。上方为原生 SVG 有向图，右侧显示选中节点的原始日志、实体定义和引用历史，下方为按日志生成的叙事摘要。逐轮原文仍可展开。

- `trace-graph.html`：独立维护的内联 CSS/JS 图谱组件，由 `render_report.py` 内嵌到交付 HTML，无外部图形库。
- 兼容 `turns` 日志和 `ontology_entities + steps` 结构。`ontology_query` 的明确记录才计查询次数；历史关联快照不反推 SPARQL 或工具调用。
- 新运行保存蓝队的 progress/citations 和 followups.ontology；未新增模型调用或业务操作。
- 引用统计范围为当前页面载入的完整历史首轮 Trace、归档实测与本页打开的新运行。每实体每轮计一次，未载入的重复试验不计入；局部 ServiceCase 按运行隔离。
- 权限允许/禁止不是动作执行；未知质保不是过保；摘要不复制未验证的 narrative_summary。
- 验证入口：`tests/browser_trace_graph.js`、`tests/browser_redblue_trace.js`、`tests/test_redblue_benchmark.py`。
