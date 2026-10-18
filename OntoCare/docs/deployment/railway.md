# Railway 部署

1. 把本目录推送到自己的私有或公开 GitHub 仓库。确认 `.env`、`uploads/`、`__pycache__/` 不在提交中。
2. Railway → New Project → Deploy from GitHub repo → 选择仓库与 `main`。`Procfile` 使用 Gunicorn 启动。
3. 在 Railway Variables 设置 `LLM_BASE_URL`、`LLM_MODEL`、`LLM_API_KEY`；如需视觉模型，再设置 `VISION_BASE_URL`、`VISION_MODEL`、`VISION_API_KEY`。只在 Railway 控制台设置真实密钥，不在代码、文档或命令行输出中粘贴。
4. 部署后在 Settings → Networking 生成域名。访问页面，输入“我的 S1 Pro 不吸了”再输入“是吸奶器”，检查右侧模型状态、订单状态与 request_id。
5. 用 `eval.py`、`eval_safe.py` 与 `tests/test_m0_flow.py` 的结果分别说明原规则、修订规则和接口流程；不要把 20/20 规则断言称为 20/20 客服问题解决率。

旧版 `run.sh` 中的密钥曾进入 Git 历史。部署前请先在对应供应商后台撤销并重建，Railway 上也应替换为新值。
