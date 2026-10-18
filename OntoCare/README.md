# OntoCare｜智能售后与经营归因工作台

## 文档导航

- [文档总览](docs/README.md)
- [技术架构](docs/architecture/system-overview.md)
- [公网部署](docs/deployment/public-demo.md)
- [模块与脚本索引](docs/architecture/module-index.md)

## 仓库结构

```text
OntoCare/
├── app.py / judge_server.py     # 本地与公网服务入口
├── *.py                        # 现有业务模块，保持导入兼容
├── docs/                       # 说明、Prompt、长尾策略与验收文档
├── scripts/                    # 数据导入、构建与打包工具
├── tests/                      # 自动化测试
├── benchmark/                  # 评测编排、配置与结果数据
├── evaluation/                 # 测试用例与原始评测数据
├── reports/                    # JSON等机器可读结果
├── data/ / knowledge/          # 业务数据与结构化知识
├── static/                     # HTML、CSS、JS与图片
└── ontocare_multimodal/         # 多模态能力模块
```

## 原有运行与功能说明


本目录是独立副本。公网部署请优先阅读 [README-公网部署.md](docs/deployment/public-demo.md)，生产入口为 `judge_server:app`。下文保留原项目说明。

# OntoCare · 安小克 Anka

安克售后 Demo：用户端与商家端两个视角。用户端支持图片、视频和语音；商家端包含邮件工作台和分析看板。演示 API 已在后端预置。

本次前端更新：处理摘要按实际进度逐行显示，完成后保留展开；两个页面使用相同的一级导航，当前项标黑。评测工作台入口已从前端移除，后端接口、算法、提示词与 AI 交互流程保持原样。历史评测源码与结果保留作证据。下文评测章节为历史实现记录。

## 运行

需要 Python 3.10+。在本目录运行：

```sh
./run.sh
```

首次运行自动创建虚拟环境并安装 requirements.txt。打开 http://127.0.0.1:5088/ 。服务已启动时无需重复启动。

演示连接已写入根目录 `demo_api_config.json`。启动时自动读取，重启后仍然生效；评委无需填写 API Key。文字问答使用 Nova Pro，图片识别使用 DeepSeek V4.1 Flash。商家端已移除模型配置页。

更换演示连接时，由开发者修改 `demo_api_config.json` 的 `api_key`、`base_url`、`text_model` 和 `vision_model` 后重启；该文件只由后端读取，网页和公开接口不返回密钥。交付打包工具会随包附带该演示配置。

## 演示入口

| 页面 | 地址 / 文件 | 建议演示 |
|---|---|---|
| 用户端 | / | 问答、逐行处理摘要、图片 / 视频 / 语音助手 |
| 商家端 | /merchant | 邮件工作台；切换功能保留当前草稿 |
| 商家端 · 分析看板 | /merchant#analytics | 工单分布、来源下钻、归因与决策 |

评测工作台默认打开「实测结果」：展示历史基线、单次修复复测、语义裁判与三次动态红蓝实验，点击可查看所属版本的 Trace。`#view=business` 为业务约束展示，`#view=principles` 为评测原理；模拟值与真实成绩分别标注。页面数据由 `benchmark/evaluation_history.py` 从保存的结果读取，运行 `benchmark/render_report.py` 重新内嵌，不会发起新评测。

「评测原理」顶部的 6 张亮点卡片可用于讲解真实数据、Persona、联合验收、重复稳定性、故障注入与回归闭环；点击按钮可打开现有原文与实验记录。

归因 HTML 可双击离线打开，已内嵌数据与 Logo，没有导出按钮。评测页数据也内嵌；图表使用 ECharts CDN，断网保留数据表与证据。用户端和商家端需要后端，不是独立静态应用。

## 五分钟评审顺序

1. 真实数据及痛点（30秒）：63工单、16订单、24商品明细、875知识条目、336经销商。
2. 用户端（90秒）：产品消歧、中文/英文跟随、知识引用、少打字选项。
3. 商家端（60秒）：原信与真实订单关联、基于事实生成草稿，仍需人工审核。
4. 经营归因（60秒）：可下钻的候选与行动建议，高管摘要直接查看。
5. 评测（60秒）：模型和规则基线的实际结果、失败项、尚未验证的生产能力。

评分维度对应：创新看“规则授权 + 模型表达 + 来源核验”；价值看真实工单处理；稳定性看失败轨迹与边界；现场展示避免依赖 PDF 导出。没有虚构提升比例或虚假全通过率。

## 结构与复现

先读 ARCHITECTURE.md；交付包附完整 源码目录树.md 和带 SHA256 的 release-manifest.json。

```sh
.venv/bin/python -m unittest discover -s tests -q
.venv/bin/python -m unittest discover -s benchmark -p 'test_*.py' -q
node tests/test_merchant_assist.js
.venv/bin/python scripts/merchant_attribution/build.py
.venv/bin/python benchmark/render_report.py
.venv/bin/python scripts/package_release.py
```

Node.js 18+ 只用于重新构建经营归因和 JS 验证，运行已构建的 Python 服务不需要 Node。重新导入 Excel 的离线工具另需 openpyxl 及用户原工作簿，运行时已提供完整 JSON 快照。

本次验证见 docs/reports/本次交付验证（2026-10-17）.md。benchmark/benchmark-results.json 是历史真实测评记录，不是本次改动后全量复测成绩；详细局限见 docs/evaluation/benchmark/README.md。

## 评测失败修复与缓存优先

先看 docs/reports/评测失败修复说明.md，再看 reports/评测失败复盘.json 的原始失败摘录。新增 action_gateway.py 统一隐藏用户响应中的订单地址；docs/knowledge/long_tail/评测修复策略库.md 保存 6 条失败处理策略。

应用层固定问答缓存命中后直接返回原知识引用，未命中再检索并调用模型。这是可审计的 FAQ/workflow 缓存，不是模型内部的 KV Cache。长尾策略不等同官方政策，订单、质保、权限仍按本轮事实核算。

本次复测见 benchmark/repair-final-results.json；历史 benchmark-results.json 保持原样。只有一轮新复测，不能据此宣称 pass^3/pass^8 或生产 SLA。

## 评测原理架构图

打开 `/benchmark.html#view=principles` 查看原理 Tab；`static/benchmark-principles.html` 为可双击打开的无外部脚本版本。图示用原生 HTML/CSS/JS 实现，复用内嵌用例与源表证据。红蓝节点下钻、来源弹窗、键盘悬停说明、移动端单列及减少动画模式均可用。“回放一轮”仅演示流程，不会发起真实评测。独立版的其他图表页保留数据表降级展示。

## 红蓝对抗后端与逐轮 Trace

见 `docs/evaluation/benchmark/INTEGRATION.md`。原理页新增“运行 P01 小样本”：离线规则或在线模型红队/蓝队/裁判，独立进程执行，返回真实 Trace。`POST /api/benchmark/run` 异步返回运行编号；状态与逐轮证据可通过 API 查询。原理图中的回放按钮仍仅为示意。动态结果不混入历史 pass^k，手动修复标记不改变评测成绩。

### 图片与视频辅助检索

上传支持 JPG/PNG/WebP、MP4/MOV/WebM，最大 25 MB。服务端视觉识别生成待核验文字描述，再进入产品知识检索及本体决策。型号无法确认时需要点选；图像不能替代购买归属证明。
图片识别复用 `demo_api_config.json` 中预置的接口与 Key，使用 `vision_model` 指定的模型；评委无需单独配置。
视频需要安装 ffmpeg，仅抽取前 30 秒内最多 6 帧，不分析音频；不是完整视频时序理解。原始上传处理后删除，识别描述仅保留于当前服务进程，重启后需重新上传。
首页订单卡片按真实购买日期降序展示，包含订单号、SKU、系列图片及源表链接；属于演示数据，不代表已认证的个人订单。


### 经营归因对话助手
在 `/analytics` 点击右下角「AI 经营归因助手」。后端 `/api/analytics/chat` 顺序执行 `ReadOntology`、`ReadTrace`，读取与看板相同的 `reports/attribution_report.json`；确定性计算统计与引用，再使用现有服务端 LLM 配置生成核查建议。无模型/无有效结果时明确展示规则摘要。
- 关键模块：`analytics_assistant.py`；提示词：`docs/prompts/agents/analytics/Agent.md`。
- 页面源：`scripts/merchant_attribution/template.html` + `assistant.html`，运行同目录 `build.py` 生成内联 HTML。
- 节点显示的是实际查询、规则定义、归因审计与来源，不是模型内部思维。RC 标签仍是待核查候选。
- 直接双击 HTML 可查看快照；AI 对话需运行 Python 服务。


### 通用产品支持与双语补充
- `general_support.py` 为充电器类别提供有官方来源的基础排查，无需先查订单；有线/无线隔离，安全与售后资格流程仍优先。
- `knowledge/long_tail/售后长尾问题双语知识库.json` 保存用户原文件（声明 310、实际 14 条）。运行时仅检索「双语补充_检索策略.json」的 14 条整理策略，保留条目 ID 和双语同义词，不直接执行原始政策承诺。
- 本次是知识检索与规则更新，不是模型参数训练。复现导入：`.venv/bin/python scripts/import_bilingual_support.py`（原始文件位于项目上级目录时）。


### 多模态长尾扩充包
40 条新增流程候选已接入长尾检索，103 条合并版保留归档，未作为新真实工单。图片/视频提示词增加模糊字段、静态图限制、票据与音频边界；证据带哈希、未核验状态及采样位置。上传结果绑定案件代次，旧案件结果不能用于新案件。详见 `docs/knowledge/long_tail/多模态扩充包_接入说明.md`。
