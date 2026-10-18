# 数据接入版

基于 ontocare-demo-safe.zip 修改，保留原页面布局。运行 `bash run.sh`，访问 http://127.0.0.1:5088；Mac 也可双击「启动.command」。首次运行需 Python 3.10+ 和联网安装依赖。HTML 依赖本地后端，不要直接双击 static/index.html 使用。

数据自动从 data/source.json 读取，这是用户提供的数据描述压缩包内完整 JSON 的副本。包含 63 工单、16 订单 / 24 明细、875 问答（872 公开）、336 经销商。更换同结构 JSON 后重启服务即可更新。页面支持选择工单、显示订单/物流明细、按 SKU 前五位检索公开问答及独立查询经销商名单。

订单延续行归入上一个明确订单号；所有原始明细保留。多商品订单未指定完整 SKU 时质保保持未知；选择工单时使用其 SKU。订单没有卖家和国家关联字段，不推定渠道授权。名单未匹配不等于非授权。物流为资料快照，质保日期按运行当天比较。

未配置模型时使用本地规则和关键词检索；不承诺多语言语义检索准确率。知识卡保留原文语言，换货等措辞是原文引用，并非执行结果。图片文件不在数据压缩包内，只保留附件引用。没有新增退款/换货执行功能。

修改：app.py、static/index.html、run.sh；新增 dataset.py、data/source.json、tests/test_dataset.py、启动.command；原流程测试适配新数据。

验证：`.venv/bin/python -m unittest discover -s tests -v`。含所有 63 工单请求、数据数量、拆单保留、产品隔离、内部知识过滤、经销商查询及原流程回归。


新增 FAQ 缓存：参见「常见问题缓存整理.md」。当前 Q&A 读取 data/qa-workbooks.json，固定答复位于 data/faq-cache.json。更新工作簿可运行 scripts/import_qa.py（离线导入工具需 openpyxl）；来源变更后旧缓存自动失效，审核后再运行 scripts/build_qa_cache.py。运行服务本身不依赖 openpyxl。
