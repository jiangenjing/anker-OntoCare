"""Per-session progress for reviewed troubleshooting answers; never executes returns."""
import re


def remember(case, pn, topic, reply, citations, translations=None):
    # Only operational guides have steps. Capability facts stay ordinary cached answers.
    if topic in ('dishwasher', 'microwave', 'recording'):
        case.pop('active_workflow', None)
        return
    # Only explicitly aligned translations may share a step cursor.
    localized_steps = {lang:[s.strip() for s in answer.splitlines() if s.strip()] for lang,answer in (translations or {}).items()}
    steps = [s.strip() for s in reply.splitlines() if s.strip()]
    case['active_workflow'] = {'pn': pn, 'topic': topic, 'steps': steps,
                              'cursor': 0, 'history': [], 'citations': citations, 'status': 'ACTIVE', 'localized_steps':localized_steps, 'step_language':case.get('response_language', 'zh' if re.search(r'[\u4e00-\u9fff]',reply) else 'en')}


def follow_up(case, text, language):
    flow = case.get('active_workflow')
    if not flow or not case.get('product') or flow['pn'] != case['product']['id']:
        return None
    if language in flow.get('localized_steps', {}):
        flow['steps'] = flow['localized_steps'][language]
        flow['step_language'] = language
    zh = language == 'zh'
    explicit = re.search(r'(?:第([一二三四五六七八九\d]+)步|step\s*(\d+))', text, re.I)
    explain = bool(re.search(r'没看懂|不明白|怎么做|解释|don.t understand|explain', text, re.I))
    failed = bool(re.search(r'还是不行|仍没恢复|试过了|没用|无效|未解决|tried everything|still (?:not|won.t)|didn.t work', text, re.I))
    next_step = bool(re.fullmatch(r'下一步[?？。 ]*|继续|next(?: step)?', text, re.I))
    resolved = bool(re.fullmatch(r'好了|解决了|恢复了|可以了|fixed|resolved|it works(?: now)?', text, re.I))
    if not (explain or failed or next_step or resolved):
        return None
    if resolved:
        flow['status'] = 'RESOLVED'; flow['history'].append({'event': 'user_reported_resolved'})
        return ('已记录：你反馈问题已解决。如果再次出现，可以继续告诉我具体情况。' if zh else 'Recorded: you reported that the issue is resolved.'), flow['citations']
    if flow.get('step_language',language) != language:
        return ('已保留之前的检查记录。当前步骤的中文说明还需核对，暂不推进到下一步。你可以查看引用资料，或选择人工复核。' if zh else
                'Your previous checks are retained. The English instructions for the current step still need verification, so I will not advance the checklist. You can check the cited guide or request human review.'), flow['citations']
    if explain:
        index = flow['cursor']
        if explicit:
            raw = explicit.group(1) or explicit.group(2)
            index = int(raw)-1 if raw.isdigit() else '一二三四五六七八九'.find(raw)
        if index < 0 or index >= len(flow['steps']):
            return ('当前没有这一步，请告诉我你指的是哪句话。' if zh else 'That step is not in this guide. Which sentence do you mean?'), flow['citations']
        return ((f"第 {index+1} 步是：{flow['steps'][index]}\n你是找不到对应部件，还是不确定如何操作？这一步暂未标记为完成。" if zh else
                 f"Step {index+1}: {flow['steps'][index]}\nAre you having trouble locating the part or performing the action? This step is not marked complete."), flow['citations'])
    if flow['status'] == 'RESOLVED':
        return ('请描述现在再次出现的现象，我会重新核对。' if zh else 'Please describe what is happening now so I can reassess.'), flow['citations']
    all_failed = bool(re.search(r'全部|都试|所有|tried everything|all steps', text, re.I))
    if next_step and flow['cursor'] >= len(flow['steps'])-1 and flow['status'] == 'ACTIVE':
        return ('已经到最后一步。请告诉我检查后的结果：恢复正常，还是问题仍然存在？' if zh else
                'This is the last step. Is the issue resolved or still present?'), flow['citations']
    flow['history'].append({'step': flow['cursor']+1, 'event': 'user_reported_failed' if failed else 'requested_next'})
    if all_failed or flow['status'] == 'NEEDS_HUMAN_REVIEW' or flow['cursor'] >= len(flow['steps'])-1:
        flow['status'] = 'NEEDS_HUMAN_REVIEW'
        return ('已记录这些检查仍未解决问题。我会保留型号、问题和检查记录供人工核查；请补充当前报错或照片。尚未提交维修、退款或换货。' if zh else
                'Recorded: these checks did not resolve the issue. The model, issue and checks are retained for human review. Please share the current error or a photo. No repair, refund or replacement has been submitted.'), flow['citations']
    flow['cursor'] += 1
    n=flow['cursor']
    return ((f"接下来检查第 {n+1} 步：{flow['steps'][n]}\n检查后告诉我结果。" if zh else
             f"Next, step {n+1}: {flow['steps'][n]}\nPlease tell me what you find."), flow['citations'])
