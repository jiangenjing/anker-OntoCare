# OntoCare 测评修复计划与执行记录

## Plan 与验收标准
1. 修复产品消歧、渠道槽位、产品使用检索：保留原36条用户用例，C10明确选择不被X10覆盖；S1 Pro未说明品类仍澄清；经销商不从收货地址推断。
2. 修复多语言和情绪：支持zh/en/nl/fr/de；界面自动跟随输入，商家可指定语言；两端情绪规则一致，不以情绪修改退款权限。
3. 修复商家统计：源表A列产品线与B列产品名独立统计；按工单去重错误码；明确码与内部码不重复计算；下钻原文行号与独立金标准对齐。
4. 修复回复稳定性：模型格式失败记录原因；物流快照与客户陈述冲突须保留；电机异响、损坏触点和排水异常不再泛化追问症状；正式/共情改写接入真实模型。
5. 完整离线回归、真实模型重点样例与浏览器交互验收；更新源码包，保留修复前结果。

## Action
- customer_signals.py：统一语言及情绪信号。
- app.py / qa_workflows.py：当前选择优先、渠道查询、外文故障识别、使用问题检索、针对性回退和模型诊断。
- grounded_response.py：五语言、短三段式、否定执行句不再误判为已执行；继续拒绝未经授权执行声明和引用。
- attribution.py：错误码提取、产品线图及周报。
- mail_workflow.py / mail_editing.py：具体邮件问题兜底、完整正文语气改写及字段保护。
- static：用户端自动语言、商家语言选项、语气按钮真实调用、情绪提示与产品线显示。
- agents/router、responder、mail、attribution：补充本次修正规范。
- tests/test_evaluation_regressions.py：新增12项相关回归检查；未修改测评金标准和源数据。

## 验证口径
- 原始115项回归和新增12项回归：127项。
- evaluation/run_suite.py：57条独立测评；离线语气改写两项不调用模型，必须由live补测。
- 历史结果：baseline-before-fixes；第一轮实测：results-live-fix-round1.json；最终实测：results-live.json。
- 真正生成邮件正文的风格、事实支持程度仍需语义审核；硬断言通过不能声称行业认证或100%真实世界准确率。
- 浏览器实查：错误码3212下钻为原表第19、28行；周报列出3212=2、2111=1、2310=1；产品线实际只有Anker eufy，不补造三条。

## 模型输出截断修复
真实返回的finish_reason=length证明部分JSON被截断。对已配置DeepSeek明确使用thinking.type=disabled，业务判断仍由规则与证据完成；界面继续展示真实处理进度，不展示内部思维链。已用同一供应商接口验证参数被接受、reasoning_tokens=0。参数参考：https://api-docs.deepseek.com/guides/thinking_mode/ 。
