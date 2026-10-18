# 模块与脚本职责索引

Python业务模块保持原名和入口；工具脚本统一归入 scripts/。分类不改变业务行为。

| 路径 | 职责（取自源码说明） |
|---|---|
| action_gateway.py | Public response projection. Never modifies the authoritative source records. |
| analytics_api.py | Read-only analytics and local review decisions; no external report delivery. |
| analytics_assistant.py | Read-only, evidence-bound merchant conversation over the workbench snapshot. |
| app.py | Anker Ontology-Driven Service Agent — MVP 后端 |
| attribution.py | Source-linked descriptive analytics. Signals are not proven causes. |
| conversation_workflow.py | Per-session progress for reviewed troubleshooting answers; never executes returns. |
| customer_signals.py | Small, explicit language and emotion signals; no business eligibility inference. |
| dataset.py | Adapt the supplied workbook JSON without discarding source rows. |
| eval.py | Golden Case 回归评测 —— 测规则层不变量（不调 LLM）。 |
| eval_safe.py | 安全版 Golden Case 回归 —— 仅将原题 06/12 的写动作预期改为人工审核。 |
| fixed_api.py | Load the owner's preconfigured judging connection on every server start. |
| followup_questions.py | Re-traverse case -> product/order -> public evidence after every answer. |
| general_support.py | Source-backed category help before transaction verification, without SKU invention. |
| grounded_response.py | Grounded conversational writing; decisions remain in the rule engine. |
| handoffs.py | Local review queue. Records requests; does not send email or connect an operator. |
| judge_server.py | Public presentation adapter. The existing chatbot and business rules are reused. |
| long_tail_knowledge.py | Retrieve curated service strategies, never treat them as verified policy facts. |
| mail_editing.py | Bounded rewriting of a merchant-supplied draft; no new business decisions. |
| mail_language.py | Mail presentation language checks; no eligibility or case-routing decisions. |
| mail_workflow.py | Merchant draft workflow: source email -> case facts -> rules -> cited draft. |
| media_understanding.py | Image or sampled-video evidence, never authoritative product/ownership facts. |
| model_demo.py | Local demonstration routes; no credentials are returned to the browser. |
| ontology_catalog.py | Read supplied ontology as data and namespace identifiers by source sheet. |
| order_cards.py | Presentation snapshots copied from individual source order rows. |
| proactive_orders.py | Demo-only source-backed order suggestions; product matching is not ownership verification. |
| qa_workflows.py | Reviewed FAQ workflows and source-scoped retrieval. No model calls here. |
| quick_replies.py | Short customer answers to the current question, never verified business facts. |
| scripts/analyze_qa.py | 辅助脚本，参见源码 |
| scripts/attribution_workbench/build.py | Build a standalone workbench from the evaluation suite and normalized long-tail library only. |
| scripts/build_qa_cache.py | Build reviewed bilingual FAQ entries from extracted workbook rows. |
| scripts/check_long_tail.py | Run ten reproducible checks against the configured model; never prints credentials. |
| scripts/import_bilingual_support.py | Import user bilingual notes as review strategies, not executable policy. |
| scripts/import_long_tail.py | Recover complete JSON entries and build a bounded review-strategy index. |
| scripts/import_mail.py | Read the supplied workbook into the merchant demo; never change the workbook. |
| scripts/import_qa.py | Read the two original XLSX files into source JSON; requires openpyxl for this offline tool. |
| scripts/merchant_attribution/build.py | Build the merchant workbench from all five imported source tables. |
| scripts/package_release.py | Create a clean, reproducible release including the owner-authorized judging connection. |
| user_experience.py | Source-backed presentation choices; never imply demo orders belong to a customer. |
