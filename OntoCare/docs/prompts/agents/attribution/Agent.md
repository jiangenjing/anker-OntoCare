# 售后经营归因职责

页面构建：scripts/merchant_attribution/build.py → static/merchant-attribution-agent.js → reports/attribution_report.json → static/analytics.html。

完整提示规范见 merchant-attribution-prompt.md。当前为确定性源表聚合与规则候选，不是独立模型进程。旧 attribution.py / analytics_api.py 为现有商家接口保留，不作为新版页面统计来源。

- 全部 63 条原始工单参与统计，产品线、产品名称分别统计。
- RC1–RC4 为可核验的调查线索，未知保持未知；RC3 不能直接认定设计缺陷。
- 地区只取客户明示国家；不使用收货仓库推断客户地区。
- 质保临界判断必须有投诉日期、匹配 SKU 的质保日期。
- 建议绑定原文行号及真实存在的规则 ID，知识绑定同 PN 的公开条目。
- 页面直接展示概览、归因行动、高管摘要；不提供生成改进报告、PDF、外部发送或下载按钮。
- 不把建议展示当作执行完成，不把历史 Benchmark 结果当作此次修改后的全量复测。
