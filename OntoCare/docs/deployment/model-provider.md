# DeepSeek 真实模型接入

模型 DeepSeek-V4.1-Flash，兼容接口 https://llmapi.paratera.com/v1/chat/completions。服务启动从 .env.local 读取配置，该文件权限为 600，不进入源码包或 HTML。

真实模型模式会先执行原有规则并检索证据，再用最近对话、已尝试步骤、允许/禁止动作和来源生成自然回复。知识缓存现在提供证据，不再跳过模型。每轮通常一次调用，因此会产生真实模型用量。引用 ID 本地校验，异常响应回退有依据的规则答复，并显示失败状态。

验证：60 项测试通过；实际 API 连接成功。实际连续两轮“吸力弱→配件和安装已经检查”均为 GROUNDED_LLM / model_calls=1 / status=OK，第二轮转向电量检查。实际第 32 行邮件生成也成功，保留 mail-32 和 r-474 引用。

新的 grounded_response.py 管理回复 Prompt；run.sh 加载本地密钥。下载源码包后需自行补入 .env.local 配置才能调用模型，不携带任何密钥。
