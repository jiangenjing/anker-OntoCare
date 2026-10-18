# Anker · OntoCare

本体驱动的智能售后、经营归因与可追溯评测工作台。

## 项目阅读

- **[打开HTML项目介绍](https://jiangenjing.github.io/anker-OntoCare/)**
- [Markdown原文](docs/参赛提交说明-新增补充版本.md)
- [技术架构图](OntoCare/docs/assets/ontocare-technical-architecture.png)
- [源码说明与启动步骤](OntoCare/README.md)
- [完整文档目录](OntoCare/docs/README.md)
- [路演材料](presentation/)

## 本地运行

```sh
cd OntoCare
bash run.sh
```

打开 http://127.0.0.1:5088/ 。模型配置参见 `OntoCare/.env.example`；也可复制 `demo_api_config.example.json` 为 `demo_api_config.json`，填写自己的配置。真实密钥不随仓库发布。

## 目录

```text
OntoCare/       源码、前端、数据、文档与测试
presentation/   HTML路演、PDF、可编辑PPT
docs/           参赛说明Markdown与HTML阅读版
```

## 版本与边界

项目介绍保留提交材料原文；技术主张需结合代码和历史评测口径阅读，规划不代表已实现。当前Demo提供建议、草稿与本地审核材料，不代表真实退款、换货或外部发送已执行。

241项测试中236项通过，其余5项在文件整理前已存在；未为发布重新运行付费模型评测。部分原文图片使用飞书临时链接，失效后需要维护者更新图片来源。
