"""Identify the current request and observable communication preferences.

Styles describe this utterance, not a persistent personality or eligibility.
"""
import re

STYLE_PATTERNS = (
    ('upset', r'生气|气死|愤怒|失望|投诉|furious|angry|frustrat|upset'),
    ('urgent', r'赶紧|尽快|着急|急着|马上|急需|urgent|asap|in a hurry'),
    ('benefit', r'赔偿|补偿|优惠|差价|多少钱|费用|免费|折扣|compensat|discount|cost|free'),
    ('technical', r'参数|固件|日志|电压|协议|故障码|错误码|firmware|voltage|diagnostic|error code'),
    ('reasoned', r'依据|为什么|原因|理由|政策条款|请解释|according to|reason|policy'),
    ('detailed', r'详细|具体步骤|逐步|一步一步|详细说明|step.by.step|in detail'),
    ('gentle', r'麻烦|谢谢|辛苦|请问|thank you|please'),
    ('unclear', r'不清楚|不知道|不太懂|没看懂|不确定|not sure|don.t know'),
)


def identify(text, previous_intent=None):
    """Return a conservative, explainable per-turn classification."""
    style = next((name for name, pattern in STYLE_PATTERNS if re.search(pattern, text, re.I)), 'neutral')
    patterns = (
        ('shipping', r'物流|发货|包裹|快递|到货|没收到|未收到|没到|订单.{0,24}到哪|shipping|shipment|tracking|deliver|package'),
        ('warranty', r'保修|质保|warranty'),
        ('capabilities', r'你(?:能|可以)怎么帮我|你能(?:做什么|帮我什么)|你能提供什么帮助|what can you (?:do|help)'),
        ('model_help', r'(?:不知道|不清楚|找不到).{0,10}型号|型号.{0,10}(?:怎么看|怎么找|哪里看)|don.t know.{0,10}model'),
        ('troubleshooting', r'故障|错误码|故障码|无法开机|不能开机|充不上|无法充电|漏水|吸力|不工作|motor.{0,30}noise|not working|error code|charging'),
        ('compensation', r'赔偿|补偿|差价|优惠|discount|compensat'),
        ('return_policy', r'(?:退货|退款|换货).{0,12}(?:政策|条款|规则|依据)|(?:政策|条款|规则).{0,12}(?:退货|退款|换货)|return policy|refund policy'),
        ('return', r'退货|退款|换货|退钱|退回|refund|return|replace(?:ment)?'),
    )
    def matches(name, pattern):
        if name == 'compensation' and re.search(r'(?:我要|我想|请|要求|尽快|申请).{0,8}(?:退货|退款|换货|退钱)', text):
            return False
        if name != 'return':
            return bool(re.search(pattern, text, re.I))
        if re.search(r'退款.{0,12}(?:到账|到帐|多久)|(?:refund).{0,25}(?:arrive|received|when)', text, re.I):
            return False
        return any(not re.search(r'(?:不想|不要|无需|不用|不需要|不必)\s*$', text[max(0, hit.start()-6):hit.start()])
                   for hit in re.finditer(pattern, text, re.I))
    request = next((name for name, pattern in patterns if matches(name, pattern)), 'unknown')
    if request == 'unknown' and previous_intent == 'return' and re.search(r'凭证|证明|receipt|proof of purchase', text, re.I):
        request = 'return_proof'
    return {'intent': request, 'style': style, 'source': 'rules'}
