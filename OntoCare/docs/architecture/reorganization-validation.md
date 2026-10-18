# 仓库整理验证记录

日期：2026-10-19。

- Markdown说明与运行时Prompt集中在 docs/；根目录保留README。
- 工具脚本从 tools/ 合并到 scripts/，测试与构建引用同步调整。
- Python语法解析通过；发布收集路径全部存在；docs下Markdown相对链接检查无缺失。
- Flask测试客户端检查用户端、经营归因、评测页面及两份归因文档，均返回200。
- 整理前后均运行241项单元测试：236项通过，3项失败、2项错误；失败条目完全一致，没有新增失败。
- 原有未通过项：
- test_rewrite_protects_fields (test_attribution.AttributionTests.test_rewrite_protects_fields)
- test_history_endpoint_and_missing_trace (test_redblue_benchmark.RedBlueTests.test_history_endpoint_and_missing_trace)
- test_api_rejects_cross_origin_and_remote_access (test_redblue_benchmark.RedBlueTests.test_api_rejects_cross_origin_and_remote_access)
- test_api_validates_ids_limits_and_offline (test_redblue_benchmark.RedBlueTests.test_api_validates_ids_limits_and_offline)
- test_new_api_launches_subprocess_without_clearing_sessions (test_redblue_benchmark.RedBlueTests.test_new_api_launches_subprocess_without_clearing_sessions)

本次未修复与文件归类无关的既有邮件语言断言及评测接口问题。未进行付费模型实测。
