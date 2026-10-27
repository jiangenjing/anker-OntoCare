"""Customer-facing structure for both model and deterministic responses."""
from pathlib import Path
import re

INSTRUCTIONS = (Path(__file__).parent / 'docs/prompts/agents/responder/SKILL.md').read_text(encoding='utf-8')


def format_reply(reply, lang, emotion, route, service_intent):
    """Add concise acknowledgement and next step without changing verified facts."""
    if lang not in ('zh', 'en') or len(re.split(r'\n\s*\n', reply.strip())) >= 3:
        return reply
    if lang == 'zh':
        if route == 'CONVERSATION_REPAIR':
            opening = '谢谢你提醒我，我会重新确认你的意思。'
        elif emotion in ('ANGRY', 'COMPLAINT_RISK', 'ANXIOUS'):
            opening = '听到你的不满，我很抱歉让你有这样的体验。'
        elif service_intent == 'shipping':
            opening = '我先帮你核对这次的物流问题。'
        else:
            opening = '我先按你说的情况来协助。'
        closing = ('你可以直接回复上面的问题，我会接着帮你确认。' if '？' in reply or '?' in reply
                   else '如果还有没解决的地方，请告诉我，我会继续帮你核对。')
    else:
        if route == 'CONVERSATION_REPAIR':
            opening = "Thank you for pointing that out. I'll check that I understand."
        elif emotion in ('ANGRY', 'COMPLAINT_RISK', 'ANXIOUS'):
            opening = "I'm sorry this has been frustrating."
        elif service_intent == 'shipping':
            opening = "I'll help check your shipping question."
        else:
            opening = "I'll help with what you've described."
        closing = ('Please reply to the question above and I can help with the next step.' if '?' in reply
                   else 'If anything remains unresolved, tell me and I can help check it.')
    return opening + '\n\n' + reply.strip() + '\n\n' + closing
