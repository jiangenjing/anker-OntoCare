# 安小克 / Anka 测评修复版

运行：在此目录双击 `启动.command`，或执行 `./run.sh`。
- 用户端：http://127.0.0.1:5088/
- 商家端：http://127.0.0.1:5088/merchant
- 归因统计：http://127.0.0.1:5088/analytics
- 测评报告：`evaluation/测评报告.html`，可独立打开。

页面源文件位于 `static/index.html`、`static/merchant.html`、`static/analytics.html`。它们调用本地Python服务，不是脱离后端也能查询数据和调用模型的单文件应用。

本机现有模型配置保留。源码ZIP不包含API密钥、虚拟环境、用户上传文件、交接记录和本地审核状态。换一台机器运行时，在项目目录新建 `.env.local`，配置 `LLM_BASE_URL`（包括实际/v1路径）、`LLM_API_KEY`、`LLM_MODEL` 和 `LLM_RESPONSE_MODE=grounded`；不要把密钥写进HTML或分享包。

核心变更与验证见 `docs/evaluation/OntoCare 测评修复计划与执行记录.md`。原始数据和测评金标准没有改动；修复前结果保留在 `evaluation/baseline-before-fixes`。

本版仍是演示：查询使用资料快照，邮件仅生成草稿，没有真实退款、换货、承运商查询或发信执行器。产品名录命中不等于购买归属核验。模型不可用时会显示有依据的回退，不伪装成模型成功。
