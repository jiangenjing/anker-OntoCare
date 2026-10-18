# OntoCare 源码架构与评审导读

先运行 ./run.sh，浏览器打开 http://127.0.0.1:5088/。归因页面和评测页面可独立查看；用户对话、邮件生成需要 Python 后端。

```text
OntoCare/
├── app.py                       HTTP 入口、会话、规则决策和模型调用
├── dataset.py                   五张源表适配，保留订单明细与原文行号
├── customer_signals.py          语言、情绪等可复用信号
├── action_gateway.py           用户响应地址隐藏，不修改源表
├── qa_workflows.py              同产品知识检索、固定问答缓存
├── conversation_workflow.py     多轮排障进度
├── grounded_response.py        有依据的回答与引用校验
├── followup_questions.py        每轮重新检索推荐问题
├── quick_replies.py             可点选补充信息
├── order_cards.py               真实订单图文卡片
├── user_experience.py           产品图片及界面辅助数据
├── mail_workflow.py             工单邮件上下文与草稿
├── mail_editing.py              改写、翻译与订单数字保护
├── handoffs.py                  本地待审核交接记录
├── general_support.py          通用产品支持，无须先提供订单
├── media_understanding.py      图片/视频抽帧转文字，保留未核验状态
├── proactive_orders.py         产品匹配候选订单与冲突处理
├── analytics_assistant.py      ReadOntology/ReadTrace 与模型经营建议
├── long_tail_knowledge.py       长尾策略检索
├── ontology_catalog.py         本体字段说明
├── attribution.py              现有商家分析接口的基础聚合
├── analytics_api.py            现有分析 API 兼容入口
├── static/                     用户端、商家端、归因页、评测页及素材
│   └── merchant-attribution-agent.js  新版全量归因规则与摘要
├── agents/                     各职责提示规范，非独立模型进程
├── data/                       源表快照、FAQ缓存、政策和邮件数据
├── knowledge/long_tail/         可检索策略与导入审计
├── tools/merchant_attribution/  归因快照及独立 HTML 构建器
├── scripts/package_release.py    明确清单打包，排除密钥和运行垃圾
├── reports/                    本次归因 JSON、摘要与验证记录
├── benchmark/                  用例、执行器、历史真实成绩与指标
├── evaluation/                 原始评测金标准与源表快照
└── tests/                      数据、业务规则、语言及交互契约测试
```

完整逐文件列表见交付包中的 `源码目录树.md`。

## 评委可核验的亮点

| 能力 | 代码入口 | 演示验证 |
|---|---|---|
| 同名产品消歧与同 PN 检索 | app.py、qa_workflows.py | S1 Pro 不直接跨扫地机/吸奶器下结论 |
| 规则限定权限、模型组织表达 | app.py、grounded_response.py | 模型回答绑定来源；退款不能由语言生成自动执行 |
| 常见问题固定工作流、长尾检索 | qa_workflows.py、long_tail_knowledge.py | 缓存命中和模型调用次数可见；此缓存不是模型内部 KV 张量缓存 |
| 少打字与语言跟随 | followup_questions.py、quick_replies.py | 中文句子夹英文型号仍中文；每轮推荐问题重新检索 |
| 商家邮件与经营归因 | mail_workflow.py、新版归因 JS | 原文→源表字段→规则候选→责任团队及建议 |
| 可审计评测 | benchmark/ | 逐次对话、硬断言、失败项、指标分母均保留 |

## 数据与调用边界

客户消息 → 语言/实体识别 → 产品消歧与订单关联 → 同产品知识检索/固定工作流 → 服务规则授权 → 模型据证据组织回复 → 引用、字段和语言校验 → UI。

经营归因：五张源表快照 → 全量 63 条工单聚合 → RC1–RC4 显式候选规则 → 来源与知识关联 → 建议动作及高管摘要。新版页面统计独立于历史评测抽样，统计与模板摘要采用确定性逻辑；右侧经营助手在读取事实与规则后调用模型组织分析建议，失败时回退规则摘要。候选归因不等于已证实的因果根因。

客服运行时读取 docs/prompts/agents/responder/Agent.md；经营助手读取 docs/prompts/agents/analytics/Agent.md，并调用模型生成受证据约束的建议。经营助手的 ReadOntology/ReadTrace 是 Python 数据选择函数，不是 SPARQL 图数据库查询。benchmark/agents/ 内有实际红队、蓝队和裁判适配器；不能仅凭其他职责 Markdown 文件宣称多个自主执行 Agent。

源表有 16 个订单号、24 行商品明细，不能把明细行当作 24 个订单。数据中的时间、国家和根因证据有缺口：不计算无依据的自然周趋势、故障率、利润影响或已达成降本比例。

## 精简方式

不重排已工作的 Python 导入结构。只在交付副本排除 .venv、缓存、真实密钥、用户会话/上传、临时截图、过程日志、重复数据导出、旧版静态归因构建器和过期报告。原工作目录保留历史，便于回溯。analytics.js 与旧分析 API 留作兼容，避免破坏现有测试及商家接口。

## 评测职责模块

`benchmark/config/prompts.py` 保存版本化红/蓝/裁判 Prompt；`benchmark/agents/` 实现角色适配；`benchmark/orchestrator/` 负责隔离运行和混沌注入；`benchmark/api.py` 提供本机运行、状态与 Trace 查询。复用原 Persona 与 110 个真实来源的测试配置（74 核心），不复制另一套数据。详细树与边界见 `docs/evaluation/benchmark/INTEGRATION.md`。
