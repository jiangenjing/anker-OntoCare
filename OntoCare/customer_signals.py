"""Small, explicit language and emotion signals; no business eligibility inference."""
import re
HIGH = r"\b(?:furious|angry|outrage|shit|bullshit|fuck\w*|scam)\b|投诉|差评|气死|太差|生气|!!!"
COMPLAINT = r"complain|ridiculous|unacceptable|lawyer|better business|起诉"
MEDIUM = r"frustrat|worried|still waiting|urgent|asap|in a hurry|担心|着急|赶紧|失望"
def emotion(text):
    if re.search(COMPLAINT,text,re.I):return 'COMPLAINT_RISK'
    if re.search(HIGH,text,re.I):return 'ANGRY'
    if re.search(MEDIUM,text,re.I):return 'ANXIOUS'
    return 'NORMAL'
def emotion_score(text):
    return {'COMPLAINT_RISK':9,'ANGRY':9,'ANXIOUS':5,'NORMAL':2}[emotion(text)]
def language(text, fallback=None, previous=None):
    if fallback in ('zh','en','nl','fr','de','es'):return fallback
    # Chinese prose takes precedence over untranslated product names and source terms.
    if re.search(r'[\u4e00-\u9fff]',text):return 'zh'
    product_only=r'(?:eufy\s+)?(?:S1 Pro(?: Wearable)?(?: Breast Pump)?|(?:Clean )?X10 Pro(?: Omni)?|Omni (?:E25|E28|C20)|SoloCam S340|C10)(?:[ ,，]*(?:T[A-Z0-9]+))?'
    if re.fullmatch(product_only,text.strip(),re.I):
        return previous if previous in ('zh','en','nl','fr','de','es') else 'zh'
    # Diagnostic field labels count alongside prose; model/SKU names do not.
    patterns={'es':r'\bpedido\b|\bllegado\b|envío|\bcomprobar\b|\bgracias\b',
              'nl':r'\bbestelling\b|\bverzonden\b|\bniet binnen\b|vriendelijke groet',
              'fr':r'nom du produit|bonjour|problème|aspirateur|\bmerci\b',
              'de':r'produktname|fehlercode|problembeschreibung|bürste|kundendienst'}
    scores={k:len(re.findall(v,text,re.I)) for k,v in patterns.items()}
    best=max(scores,key=scores.get)
    if scores[best]>=2:return best
    if re.search(r"\b(?:yes|no|hello|hi|thanks|thank|please|help|resolved|next|fixed|where|when|why|how|what|my|I|still|received|arrived)\b", text, re.I):return 'en'
    if len(re.findall(r'\b[a-zA-Z]{2,}\b',text))>=5:return 'en'
    return previous if previous in ('zh','en','nl','fr','de','es') else 'zh'


def reply_matches_language(reply, language):
    """Reject obvious wrong-language generated prose; source documents stay unchanged."""
    has_chinese = bool(re.search(r'[\u4e00-\u9fff]', reply))
    return has_chinese if language == 'zh' else (not has_chinese if language == 'en' else True)
