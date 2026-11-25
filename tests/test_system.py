import contextlib
import copy
import io
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from accounting.core import ROOT,load,save,balanced,reports,digest
from accounting.documents import Store
from accounting.workflow import Case,check_arguments
from accounting.extraction import validate_extraction
from accounting.runner import run
from accounting.approval import approve
from accounting.deepseek import DeepSeekClient,CallBudget,APIError
from tests.fakes import ScriptedModel,tool_call

class SystemTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.truth=load(ROOT/'data/ground_truth/expected.json')
        cls.gold=cls.truth['cases']
        cls.records={did:r for case in cls.gold for did,r in case['records'].items()}

    def store(self):
        return Store()

    def silence(self):
        return contextlib.redirect_stdout(io.StringIO())

    def test_dataset_complete_english_and_balanced(self):
        store=self.store()
        self.assertEqual((len(store.docs),len(store.invoices),len(store.bank)),(264,100,101))
        self.assertEqual(sum(not c['expected_issue_codes'] for c in self.gold),70)
        for d in store.docs.values():
            self.assertNotRegex(d['text'],r'[\u3400-\u9fff]')
        for c in self.gold:
            if c['expected_lines']:
                self.assertTrue(balanced(c['expected_lines']))

    def test_fast_path_never_calls_model(self):
        with tempfile.TemporaryDirectory() as d,self.silence():
            model=ScriptedModel(self.records)
            out=run('hybrid',limit=3,output=Path(d)/'run',client=model)
            self.assertEqual(model.calls,0)
            self.assertEqual(sum(r['status']=='PENDING_APPROVAL' for r in load(out/'cases.json')),3)
            self.assertEqual(load(out/'ledger.json'),[])

    def test_offline_unknown_template_stays_for_review(self):
        with tempfile.TemporaryDirectory() as d,self.silence():
            out=run('offline',limit=6,output=Path(d)/'run')
            rows=load(out/'cases.json')
            self.assertEqual([r['status'] for r in rows[:3]],['PENDING_APPROVAL']*3)
            self.assertEqual([r['status'] for r in rows[3:]],['REVIEW_REQUIRED']*3)
            self.assertEqual(load(out/'run_info.json')['model_calls'],0)

    def test_unsupported_documents_use_actual_extraction_contract_and_tools(self):
        store=self.store();gold=self.gold[3];model=ScriptedModel(self.records);events=[]
        from accounting.extraction import extract
        extract(store,gold['invoice_id'],model,events.append,{})
        case=Case(store,gold['invoice_id'],model,events.append)
        row=case.investigate()
        self.assertEqual(row['status'],'PENDING_APPROVAL')
        self.assertEqual(row['lines'],gold['expected_lines'])
        self.assertTrue(any(e['event']=='tool_call' and e['name']=='extract_document' for e in events))
        self.assertFalse(row['posted'])

    def test_all_cases_with_scripted_model_and_exact_manual_approval(self):
        with tempfile.TemporaryDirectory() as d,self.silence():
            model=ScriptedModel(self.records)
            out=run('hybrid',100,Path(d)/'run',client=model)
            rows=load(out/'cases.json')
            self.assertEqual(sum(r['status']=='PENDING_APPROVAL' for r in rows),70)
            expected={c['invoice_id']:c for c in self.gold}
            for row in rows:
                g=expected[row['invoice_id']]
                if not g['expected_issue_codes']:
                    self.assertEqual(row['lines'],g['expected_lines'])
                else:
                    self.assertEqual(row['status'],'REVIEW_REQUIRED')
            decisions=load(out/'review_template.json')
            for decision in decisions.values():
                decision['decision']='approve'
            save(out/'decisions.json',decisions)
            approve(out,out/'decisions.json')
            self.assertEqual(load(out/'reports.json')['balances'],self.truth['expected_full_approved_balances'])
            self.assertFalse(load(out/'run_info.json')['live_api_verified'])

    def test_model_cannot_finish_ready_before_validation(self):
        case=Case(self.store(),self.gold[0]['invoice_id'])
        with self.assertRaises(ValueError):
            case.finish_case('ready','Bypass attempt',[])

    def test_changed_bank_selection_invalidates_draft(self):
        case=Case(self.store(),self.gold[0]['invoice_id']);case.build_draft()
        case.select_bank_matches(case.bank_ids)
        with self.assertRaises(ValueError):
            case.finish_case('ready','Stale validation',[])

    def test_no_ground_truth_or_arbitrary_file_tool(self):
        with self.assertRaises(ValueError):
            check_arguments('read_ground_truth',{})
        case=Case(self.store(),self.gold[0]['invoice_id'])
        with self.assertRaises(ValueError):
            case.read_document('../ground_truth/expected.json')

    def test_fabricated_extraction_quote_is_rejected(self):
        record=self.records[self.gold[3]['invoice_id']]
        with self.assertRaises(ValueError):
            validate_extraction({'record':record,'evidence':[{'field':'number','quote':'invented quotation'}]},'Actual text')

    def test_source_conflict_cannot_be_drafted(self):
        store=self.store();g=next(c for c in self.gold if c['expected_issue_codes']==['CONTRACT_INVOICE_MISMATCH'])
        store.records.update(g['records'])
        case=Case(store,g['invoice_id'])
        self.assertIn('CONTRACT_INVOICE_MISMATCH',case.check_case()['issue_codes'])
        with self.assertRaises(ValueError):
            case.build_draft()

    def test_claim_issuer_can_be_employee_without_weakening_receipt_check(self):
        store=self.store();g=self.gold[2]
        store.records.update(copy.deepcopy(g['records']))
        claim_id=next(d for d,r in g['records'].items() if r['type']=='claim')
        receipt_id=next(d for d,r in g['records'].items() if r['type']=='receipt')
        store.records[claim_id]['issuer']=store.records[claim_id]['employee']
        case=Case(store,g['invoice_id'])
        self.assertTrue(case.check_case()['passed'])
        store.records[receipt_id]['issuer']='Unrelated Merchant (TEST)'
        feedback=case.check_case()
        self.assertIn('REIMBURSEMENT_EVIDENCE_MISMATCH',feedback['issue_codes'])
        self.assertTrue(any(d['document_id']==receipt_id and d['field']=='issuer' for d in feedback['details']))

    def test_document_type_alias_is_normalized(self):
        from accounting.extraction import validate_extraction
        record={k:None for k in self.records[self.gold[0]['invoice_id']]}
        record['type']='expense_claim'
        self.assertEqual(validate_extraction({'record':record,'evidence':[]},'Employee claim')['type'],'claim')

    def test_receipt_payer_payee_roles_require_both_employee_and_merchant(self):
        store=self.store();g=self.gold[2];store.records.update(copy.deepcopy(g['records']))
        receipt_id=next(d for d,r in g['records'].items() if r['type']=='receipt')
        invoice=store.records[g['invoice_id']];receipt=store.records[receipt_id]
        receipt['issuer']=receipt['employee'];receipt['recipient']=invoice['issuer']
        self.assertTrue(Case(store,g['invoice_id']).check_case()['passed'])
        receipt['recipient']='Unrelated Merchant (TEST)'
        self.assertIn('REIMBURSEMENT_EVIDENCE_MISMATCH',Case(store,g['invoice_id']).check_case()['issue_codes'])

    def test_failed_reextraction_preserves_prior_valid_record(self):
        store=self.store();did=self.gold[3]['invoice_id']
        store.records[did]=copy.deepcopy(self.records[did]);store.origins[did]='deepseek_extraction'
        original=copy.deepcopy(store.records[did])
        case=Case(store,did,client=ScriptedModel(self.records),attempts={did:3})
        with self.assertRaises(ValueError):
            case.reextract_document(did)
        self.assertEqual(store.records[did],original)

    def test_explicit_party_headers_override_inferred_roles(self):
        store=self.store();g=self.gold[3]
        did=next(d for d,r in g['records'].items() if r['type']=='acceptance')
        r=copy.deepcopy(g['records'][did]);r['issuer'],r['recipient']=r['recipient'],r['issuer']
        with self.assertRaisesRegex(ValueError,'Explicit source role'):
            validate_extraction({'record':r,'evidence':[]},store.docs[did]['text'])

    def test_recheck_uses_saved_records_without_api_or_posting(self):
        from accounting.recheck import recheck
        with tempfile.TemporaryDirectory() as d,self.silence():
            source=run('offline',3,Path(d)/'source')
            with patch('urllib.request.urlopen',side_effect=AssertionError('Network must not be called')):
                out=recheck(source,Path(d)/'rechecked')
            self.assertEqual(load(out/'run_info.json')['model_calls'],0)
            self.assertEqual(load(out/'ledger.json'),[])
            self.assertTrue(all(r['status']=='PENDING_APPROVAL' for r in load(out/'cases.json')))

    def test_duplicates_detected_even_in_a_single_invoice_run(self):
        g=next(c for c in self.gold if c['expected_issue_codes']==['DUPLICATE_DOCUMENT'])
        case=Case(self.store(),g['invoice_id'])
        self.assertIn('DUPLICATE_DOCUMENT',case.check_case()['issue_codes'])

    def test_receipt_payment_to_employee_is_valid(self):
        case=Case(self.store(),self.gold[2]['invoice_id'])
        self.assertTrue(case.check_case()['passed'])
        self.assertNotEqual(case.store.records[case.invoice_id]['issuer'],case.store.bank[case.bank_ids[0]]['counterparty'])

    def test_split_payment_is_not_an_error(self):
        g=next(c for c in self.gold if not c['expected_issue_codes'] and len(c['bank_ids'])==2)
        store=self.store();store.records.update(g['records'])
        self.assertTrue(Case(store,g['invoice_id']).check_case()['passed'])

    def test_wrong_and_reused_bank_rows_are_rejected(self):
        case=Case(self.store(),self.gold[0]['invoice_id'])
        with self.assertRaises(ValueError):
            case.select_bank_matches(self.gold[1]['bank_ids'])
        with self.assertRaises(ValueError):
            case.select_bank_matches(case.bank_ids*2)

    def test_report_rejects_unbalanced_journal(self):
        with self.assertRaises(ValueError):
            reports(self.store().config,[dict(invoice_id='test',lines=[{'account':'1002','debit':1,'credit':0}])])

    def test_manual_decision_hash_must_match(self):
        with tempfile.TemporaryDirectory() as d,self.silence():
            out=run('offline',3,Path(d)/'run')
            decisions=load(out/'review_template.json');first=next(iter(decisions))
            decisions[first]={'decision':'approve','snapshot_hash':'changed'}
            save(out/'decisions.json',decisions)
            with self.assertRaises(ValueError):
                approve(out,out/'decisions.json')

    def test_api_budget_prevents_network_call(self):
        with patch.dict(os.environ,{'DEEPSEEK_API_KEY':'unit-test-placeholder'}):
            client=DeepSeekClient(max_calls=0)
            with self.assertRaises(CallBudget):
                client.chat([],role='test')

    def test_api_wire_format_and_usage(self):
        response={'model':'mock','id':'mock-id','usage':{'prompt_tokens':7},
                  'choices':[{'finish_reason':'tool_calls','message':tool_call('check_case')}]}
        with patch.dict(os.environ,{'DEEPSEEK_API_KEY':'unit-test-placeholder'}):
            client=DeepSeekClient()
            with patch('urllib.request.urlopen',return_value=io.BytesIO(json.dumps(response).encode())) as network:
                client.chat([{'role':'user','content':'English test'}],role='test',tools=[])
                self.assertEqual(network.call_args.args[0].full_url,'https://api.deepseek.com/chat/completions')
                self.assertEqual(client.usage[0]['usage']['prompt_tokens'],7)

    def test_empty_json_is_not_a_rule_fallback(self):
        with patch.dict(os.environ,{'DEEPSEEK_API_KEY':'unit-test-placeholder'}):
            client=DeepSeekClient()
            with patch.object(client,'chat',return_value={'content':' '}):
                with self.assertRaises(ValueError):
                    client.json_object('JSON',{},role='test')

    def test_api_failure_is_saved_and_does_not_claim_success(self):
        class FailedModel:
            model='failed-test-model';calls=1;usage=[];is_test_double=True
            def json_object(self,*args,**kwargs):
                raise APIError('Simulated API outage')
        with tempfile.TemporaryDirectory() as d,self.silence():
            out=run('hybrid',6,Path(d)/'run',client=FailedModel())
            self.assertIn('API_UNAVAILABLE',load(out/'cases.json')[3]['issue_codes'])
            self.assertFalse(load(out/'run_info.json')['live_api_verified'])

if __name__=='__main__':
    unittest.main()
