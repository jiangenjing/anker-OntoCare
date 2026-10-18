"""Mail presentation language checks; no eligibility or case-routing decisions."""
import re

NAMES = {'zh': '中文', 'en': 'English', 'de': 'Deutsch', 'fr': 'Français', 'nl': 'Nederlands'}
WORDS = {
    'en': set('the this that your you our we is are was were not please for with from have has been can cannot will order tracking request support thank hello received provide issue'.split()),
    'de': set('der die das dem den ein eine einen und ist sind nicht bitte sie ihre ihr ihren für wir wurde werden mit von zum zur bei auf kann können dass bestellung sendung anfrage vielen dank nachricht kundendienst'.split()),
    'fr': set('le la les un une des du et est sont pas ne veuillez vous votre vos pour avec nous dans sur peut commande demande merci bonjour contacter assistance reçu'.split()),
    'nl': set('de het een en is zijn niet alstublieft u uw voor met van wij ons onze op bij kan kunt bestelling zending bericht bedankt hallo klantenservice betreft hulpvraag'.split()),
}
FORMULAS = {
    'en': r'(?im)^\s*(?:Dear Customer\b|Hello[,!]|Thank you for contacting|Best regards\b|Anker Support Team\s*$)',
    'de': r'(?im)^\s*(?:Guten Tag\b|vielen Dank\b|Mit freundlichen Grüßen\b|Anker Kundendienst\s*$)',
    'fr': r'(?im)^\s*(?:Bonjour\b|Merci de nous\b|Cordialement\b|Service client Anker\s*$)',
    'nl': r'(?im)^\s*(?:Bedankt voor\b|Met vriendelijke groet\b|Anker Klantenservice\s*$)',
}


def scores(text):
    tokens = re.findall(r"[^\W\d_]+", text.lower(), re.UNICODE)
    return {lang: sum(word in words for word in tokens) for lang, words in WORDS.items()}


def detect(text, fallback='en'):
    if re.search(r'[\u4e00-\u9fff]', text):
        return 'zh'
    counts = scores(text)
    for lang, pattern in {'de': r'produktname|fehlercode|problembeschreibung',
                          'fr': r'bonjour|problème|nom du produit',
                          'nl': r'bestelling|vriendelijke groet'}.items():
        counts[lang] += 2 * len(re.findall(pattern, text, re.I))
    best = max(counts, key=counts.get)
    return best if counts[best] >= 3 else fallback


def matches(text, language):
    """Conservative rejection of obvious mixed prose, allowing brands and model IDs.

    This is a consistency check, not a semantic/factual certification.
    """
    if language not in NAMES or not isinstance(text, str) or not text.strip():
        return False
    if any(re.search(pattern, text) for lang, pattern in FORMULAS.items() if lang != language):
        return False
    chinese = bool(re.search(r'[\u4e00-\u9fff]', text))
    if language == 'zh':
        if not chinese:
            return False
        # Product names and identifiers are fine; an English prose sentence is not.
        for part in re.split(r'\n\s*\n|[。！？]', text):
            latin = ' '.join(re.findall(r'[a-zA-Z][a-zA-Z\s\-,:;.!?\u00c0-\u024f]{8,}', part))
            if len(re.findall(r'[a-zA-Z]{2,}', latin)) >= 8 and max(scores(latin).values(), default=0) >= 4:
                return False
        return True
    if chinese:
        return False
    total = scores(text)
    if language != 'en' and total[language] < 2:
        return False
    others = [value for lang, value in total.items() if lang != language]
    if language == 'en' and total['en'] == 0 and max(others, default=0) > 0:
        return False
    if max(others, default=0) >= max(4, total[language] * 1.35):
        return False
    for part in re.split(r'\n\s*\n|(?<=[.!?])\s+', text):
        count = scores(part)
        other = max((value for lang, value in count.items() if lang != language), default=0)
        if other >= max(4, count[language] * 1.5):
            return False
    return True


def finalize(draft, language, call=None):
    """Localize a completed draft only if needed, after the existing business rules."""
    if language != 'zh':
        # Source-table field values can contain Chinese even in an English reply.
        # These fixed display translations preserve missing/estimated status.
        words = {
            'en': ('not provided', 'not confirmed', 'breast pump', 'robot vacuum', 'pre-order item; expected dispatch on {}'),
            'de': ('nicht angegeben', 'nicht bestätigt', 'Milchpumpe', 'Saugroboter', 'Vorbestellung; voraussichtlicher Versand am {}'),
            'fr': ('non fourni', 'non confirmé', 'tire-lait', 'robot aspirateur', 'précommande ; expédition prévue le {}'),
            'nl': ('niet opgegeven', 'niet bevestigd', 'borstkolf', 'robotstofzuiger', 'voorbestelling; verwachte verzending op {}'),
        }[language]
        for field in ('draft', 'subject'):
            for original, translated in zip(('未提供', '未确定', '吸奶器', '扫地机'), words):
                draft[field] = draft[field].replace(original, translated)
            draft[field] = re.sub(r'预售产品，预计(\d{4}/\d{1,2}/\d{1,2})发货',
                                  lambda match: words[4].format(match.group(1)), draft[field])
    if not matches(draft['draft'], language) or not matches(draft['subject'], language):
        if call is None:
            raise ValueError('邮件未通过目标语言检查，请连接模型后重新生成。')
        import mail_editing
        translated = mail_editing.rewrite(call, draft['draft'], 'translate', language,
                                         subject=draft['subject'])
        draft['draft'] = translated['text']
        draft['subject'] = translated['subject']
    draft['language'] = language
    draft['trace']['response_language'] = language
    draft['checks'].append({'rule': '邮件语言', 'status': NAMES[language],
                            'detail': '主题与正文通过语言一致性检查；品牌、型号、订单号与引用保留，事实仍需核对。'})
    return draft
