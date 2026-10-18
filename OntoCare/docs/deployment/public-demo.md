# OntoCare 评委公网版

这是独立复制的评委版本。原来的本体检索、售后决策、知识引用和 AI 交互沿用原实现；新增的界面和部署入口在本目录内，不改原提交版。

评委进入网页后无需配置 API。默认文字问答使用 Nova Pro，图片识别使用 DeepSeek V4.1 Flash。

## 已准备的页面

- `/`：用户问答、真实进度摘要、来源引用、对话图谱与多模态助手。
- `/merchant`：邮件工作台与彩色分析看板。
- 手机端提供独立“图谱”入口，展开后点击节点可回到对应问题。

## 部署到已有服务器

目录内已有 `demo_api_config.json`。将整个目录传到自己的服务器，安装 Docker 后运行：

```sh
docker compose up -d --build
```

服务监听服务器的 8080 端口；由服务器的反向代理或云平台配置 HTTPS 域名。配置文件以只读方式挂载，重启无需填写 Key。`compose.yaml` 会在主机重启后自动启动服务。

没有 Docker 时，可以用 `bash run-online.sh` 启动，再交给服务器的进程管理工具保持运行。

## Railway 或 Render

已提供 `Dockerfile`、`railway.json` 和 `render.yaml`。Docker 镜像不包含 API Key；由部署人员把同一个 Key 保存为云平台的 `COMPETITION_API_KEY`，之后评委无需配置。模型分工已写入默认设置。

Render 配置默认使用免费实例；是否需要常驻实例由账号所有者选择。正式公网链接以云平台实际部署成功后的 HTTPS 地址为准。

启动命令固定使用一个工作进程并开启多线程，以保留原有会话状态的处理方式。不要直接增加工作进程数量。

## 验证入口

访问 `/api/judge-health` 应返回 `status: ready` 和 `configured: true`，不返回 Key。

本地验收预览地址不等于长期公网地址；需要云服务器或托管平台账号才能完成最终发布。
