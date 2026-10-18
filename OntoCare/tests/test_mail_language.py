import copy
import json
import unittest
from unittest.mock import Mock
import mail_editing
import mail_language

TEXT = {
    'zh': '您好，请提供订单 Anker007 的购买凭证。型号 T2080 的错误码 EB1L 仍需核查，尚未批准换货。 [2]',
    'en': 'Hello, please provide proof of purchase for order Anker007. Error EB1L on T2080 still needs review; a replacement has not been approved. [2]',
    'de': 'Guten Tag, bitte senden Sie den Kaufbeleg für Ihre Bestellung Anker007. Der Fehler EB1L bei T2080 muss noch geprüft werden; ein Austausch wurde nicht genehmigt. [2]',
    'fr': 'Bonjour, veuillez fournir la preuve d’achat de votre commande Anker007. Le code EB1L du T2080 doit encore être vérifié ; le remplacement n’est pas approuvé. [2]',
    'nl': 'Hallo, stuur ons uw aankoopbewijs voor bestelling Anker007. De fout EB1L op T2080 moet nog worden gecontroleerd; een vervanging is niet goedgekeurd. [2]',
}
SUBJECT = {'zh': '关于您的咨询 — T2080', 'en': 'Re: Your support request — T2080',
           'de': 'Betreff: Ihre Anfrage — T2080', 'fr': 'Objet : votre demande — T2080',
           'nl': 'Betreft: uw hulpvraag — T2080'}


class MailLanguageTests(unittest.TestCase):
    def test_supported_languages_and_cross_language_rejection(self):
        for lang, text in TEXT.items():
            with self.subTest(lang=lang):
                self.assertTrue(mail_language.matches(text, lang))
                self.assertTrue(mail_language.matches(SUBJECT[lang], lang))
                self.assertFalse(mail_language.matches(text, 'en' if lang != 'en' else 'de'))

    def test_mixed_paragraphs_are_rejected_but_brand_names_are_allowed(self):
        self.assertFalse(mail_language.matches(TEXT['zh'] + '\n\nPlease provide your order and proof of purchase.', 'zh'))
        self.assertFalse(mail_language.matches(TEXT['de'] + '\n\nPlease provide your order and proof of purchase.', 'de'))
        self.assertTrue(mail_language.matches('您好，eufy S1 Pro T2080 的错误码 EB1L 需要核查。', 'zh'))
        self.assertFalse(mail_language.matches(TEXT['de'] + '\n\nAnker Support Team', 'de'))
        self.assertFalse(mail_language.matches('Bonjour, votre commande', 'en'))

    def test_fixed_source_values_preserve_missing_and_estimated_status_without_a_model(self):
        draft = {'draft': 'Hello, your order Anker007 has carrier 未提供; tracking 未提供.\n\nDispatch: 预售产品，预计2026/10/20发货.',
                 'subject': SUBJECT['en'], 'trace': {}, 'checks': []}
        result = mail_language.finalize(draft, 'en')
        self.assertIn('not provided', result['draft'])
        self.assertIn('expected dispatch on 2026/10/20', result['draft'])
        self.assertNotRegex(result['draft'], r'[\u4e00-\u9fff]')

    def test_explicit_translation_validates_subject_and_protected_facts_for_all_languages(self):
        for lang in TEXT:
            call = Mock(return_value=json.dumps({'text': TEXT[lang], 'subject': SUBJECT[lang]}))
            out = mail_editing.rewrite(call, TEXT['en'], 'translate', lang, subject=SUBJECT['en'])
            self.assertEqual(out['text'], TEXT[lang])
            payload = json.loads(call.call_args.args[1])
            self.assertEqual(payload['language'], lang)
            self.assertIn('EB1L', payload['protected_literals'])

    def test_wrong_language_or_changed_identifiers_do_not_return_a_successful_edit(self):
        for body in [TEXT['en'], TEXT['de'].replace('Anker007', 'Anker008'), TEXT['de'].replace('EB1L', 'EB2L')]:
            with self.assertRaises(ValueError):
                mail_editing.rewrite(lambda *a, **kw: json.dumps({'text': body}), TEXT['en'], 'translate', 'de')
        with self.assertRaises(ValueError):
            mail_editing.rewrite(lambda *a, **kw: json.dumps({'text': TEXT['de'], 'subject': SUBJECT['en']}), TEXT['en'], 'translate', 'de', subject=SUBJECT['en'])

    def test_equivalent_identifier_case_and_dates_restore_original_format_only(self):
        original='Order ANKER007; SKU T2080GA1; date 2026-09-08. [2]'
        translated='订单 Anker007；型号 t2080ga1；日期 2026年9月8日。 [2]'
        restored=mail_editing.restore_literal_format(translated,original)
        self.assertIn('ANKER007',restored)
        self.assertIn('T2080GA1',restored)
        self.assertIn('2026-09-08',restored)
        self.assertEqual(mail_editing.protected(original),mail_editing.protected(restored))
        changed=mail_editing.restore_literal_format(translated.replace('9月8日','9月9日'),original)
        self.assertNotEqual(mail_editing.protected(original),mail_editing.protected(changed))

    def test_final_language_correction_preserves_existing_case_decisions_and_citations(self):
        draft = {'draft': TEXT['en'], 'subject': SUBJECT['de'], 'route': 'SAFETY_REVIEW',
                 'citations': [{'id': 'service-rules'}], 'trace': {'answer_route': 'SAFETY_REVIEW'}, 'checks': []}
        original = copy.deepcopy(draft)
        call = Mock(return_value=json.dumps({'text': TEXT['de'], 'subject': SUBJECT['de']}))
        result = mail_language.finalize(draft, 'de', call)
        self.assertEqual(result['route'], original['route'])
        self.assertEqual(result['citations'], original['citations'])
        self.assertEqual(result['trace']['answer_route'], original['trace']['answer_route'])
        self.assertEqual(result['language'], 'de')
        call.assert_called_once()

    def test_valid_drafts_need_no_model_and_invalid_offline_drafts_are_not_mislabeled(self):
        for lang in TEXT:
            draft = {'draft': TEXT[lang], 'subject': SUBJECT[lang], 'trace': {}, 'checks': []}
            call = Mock()
            mail_language.finalize(draft, lang, call)
            call.assert_not_called()
        with self.assertRaises(ValueError):
            mail_language.finalize({'draft': TEXT['en'], 'subject': SUBJECT['de']}, 'de')

    def test_auto_detection_distinguishes_western_languages(self):
        for lang, text in TEXT.items():
            self.assertEqual(mail_language.detect(text), lang)


if __name__ == '__main__':
    unittest.main()
