"""Source-backed category help before transaction verification, without SKU invention."""
import re

SOURCE='https://service.anker.com/article-description/Anker-charger-not-charge-at-all'
SLOW='https://service.anker.com/article-description/What-should-I-do-if-my-wall-charger-charges-slowly'
CITATION={'id':'official-charger-general','kind':'knowledge','label':'Anker 官方支持 · 充电器通用排查（按设备类别）','url':SOURCE}


def prepare(case,text,known_product=False):
    named=bool(re.search(r'充电器|适配器|\bcharger\b|\badapter\b',text,re.I))
    other=bool(re.search(r'扫地|机器人|吸奶|robot|vacuum|breast pump|充电宝|power bank',text,re.I))
    if known_product or other:
        case.pop('general_support',None);return
    if named:
        category='wireless' if re.search(r'无线|wireless|magsafe',text,re.I) else 'wall'
        case['general_support']={'category':category}
        # A new category must not inherit another product's warranty or workflow.
        for k in ('product','order_id','selected_sku','selected_tracking','last_issue','active_workflow','purchase_channel_claim'):
            case.pop(k,None)
        case['product']=None
        case.update(warranty='UNKNOWN',dealer='UNKNOWN',troubleshooting='NOT_STARTED')


def answer(case,text,lang):
    context=case.get('general_support')
    if not context or lang not in ('zh','en'):return None
    # Category context only applies to follow-ups, never arbitrary unrelated prompts.
    if not re.search(r'充电|线|插座|快充|手机|试过|不行|好了|解决|兼容|材料|charger|charg|cable|outlet|phone|tried|work|resolved|compatible',text,re.I):return None
    if re.search(r'退款|换货|保修|质保|订单|物流|refund|replacement|warranty|order|shipping|tracking',text,re.I):return None
    zh=lang=='zh';wireless=context['category']=='wireless'
    citation=dict(CITATION)
    if re.search(r'慢|快充|兼容|slow|fast|compatible',text,re.I):
        citation.update(id='official-charger-speed',url=SLOW,label='Anker 官方支持 · 有线充电速度排查')
        if wireless:return None
        reply=('快充需要手机与充电器支持相同的充电协议，线缆也会影响结果。可以先换一条兼容线缆、换个插座测试。\n\n如果要核对具体兼容性，请告诉我手机型号和充电器标签上的型号；这一步不用提供订单号。' if zh else 'Fast charging requires compatible charging technology on both the phone and charger. Try another compatible cable and outlet.\n\nTo check specific compatibility, share the phone model and the model printed on the charger. An order number is not needed for this check.')
    elif re.search(r'试过|还是不行|tried|still.*(?:not|work)',text,re.I):
        reply=('了解，通用排查后仍未恢复。请告诉我手机型号，以及换线、换插座、换设备后的结果，我帮你缩小范围。若需要申请维修或保修，再通过售后渠道核验购买凭证和序列号；目前不能直接确定是硬件损坏。' if zh else 'The basic checks have not resolved it. Please share your phone model and what happened with another cable, outlet and device so we can narrow it down. Purchase evidence and the serial number are needed later if you request service or warranty review. This does not confirm a hardware fault.')
    elif re.search(r'解决了|好了|resolved',text,re.I):
        reply='太好了，已经恢复充电。后续如果再次出现，可以记录当时使用的线缆和设备，便于排查。' if zh else 'Glad charging is working again. If it recurs, note the cable and device you were using to help narrow it down.'
    elif wireless:
        reply=('理解，先排查无线充电，不用先找订单号。\n\n1. 重启手机，取下手机壳后重试。\n2. 换一条兼容线缆测试；供电适配器应符合该款无线充电器的要求。\n3. 用另一部支持无线充电的手机测试。\n\n你用的是磁吸还是普通无线充电器？确认类型后，我再帮你核对供电要求。' if zh else 'Let’s check wireless charging first; no order number is needed.\n\n1. Restart the phone and retry without its case.\n2. Try another compatible cable and a power adapter suitable for your charger.\n3. Test another phone that supports wireless charging.\n\nIs this a magnetic or non-magnetic wireless charger? That helps us check its input requirements.')
    else:
        reply=('理解，充电器无法给手机充电确实不方便。可以先按安克官方的有线充电器通用方法排查，不用先找订单号。\n\n1. 从插座拔下充电器，并断开所有线缆和设备，等待 5 分钟后重新连接。\n2. 更换一条兼容且正常工作的充电线，再换一个插座测试。\n3. 尝试给另一部设备充电，观察是否只有当前手机无法充电。\n\n试完后告诉我哪一步有变化；如果仍不行，再补充手机型号，我继续帮你排查。' if zh else 'I understand your charger will not charge your phone. Start with Anker’s general wired-charger checks; no order number is needed.\n\n1. Unplug the charger and disconnect all cables and devices. Wait 5 minutes before reconnecting.\n2. Try another compatible, working cable and a different outlet.\n3. Test another device to see whether only this phone is affected.\n\nLet me know what changes. If it still fails, share your phone model so we can narrow it down.')
    return {'reply':reply,'source':citation}


def followups(case,data):
    if not case.get('general_support'):return data
    data['general_support']=True
    wireless=case['general_support']['category']=='wireless'
    pairs=[('无线充电和手机壳有关系吗？','Can my phone case affect wireless charging?')] if wireless else [('充电器充电很慢，怎么排查？','My charger charges slowly. What should I check?')]
    pairs += [('这些方法试过了，还是不行','I tried these checks, but it still does not work.'),('解决了，已经能充电了','Resolved, charging works again.')]
    data['questions']=[{'text':zh,'text_en':en,'source_ids':['official-charger-speed' if ('很慢' in zh) else CITATION['id']]} for zh,en in pairs]
    data['ontology']['nodes']=[{'id':'case','type':'ServiceCase'},{'id':CITATION['id'],'type':'KnowledgeItem'},{'id':'official-charger-speed','type':'KnowledgeItem'}]
    data['ontology']['edges']=[{'from':'case','to':CITATION['id'],'relation':'references'}]
    data['ontology']['product']=None
    data['ontology']['edges'].append({'from':'case','to':'official-charger-speed','relation':'references'})
    data['ontology']['retrieved_count']=2
    return data
