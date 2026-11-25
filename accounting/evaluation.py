"""Only evaluation code reads ground truth. Scores never enter runtime context."""
from pathlib import Path
from .core import ROOT,load,save

def normalize(lines):
    return sorted((x['account'],x['debit'],x['credit']) for x in lines)

def evaluate(output,truth_path=None):
    out=Path(output);rows=load(out/'cases.json');info=load(out/'run_info.json')
    truth=load(truth_path or ROOT/'data/ground_truth/expected.json')
    gold={x['invoice_id']:x for x in truth['cases']}
    ids={r['invoice_id'] for r in rows}
    if len(ids)!=len(rows) or ids!=set(info['selected_invoice_ids']) or ids-set(gold):
        raise ValueError('Incomplete, duplicate or unknown evaluation results')
    field_ok=field_total=normal=exact=tp=fp=fn=issue_exact=0
    by_split={}
    for row in rows:
        g=gold[row['invoice_id']];bad=bool(g['expected_issue_codes']);held=row['status']=='REVIEW_REQUIRED'
        tp+=bad and held;fp+=not bad and held;fn+=bad and not held
        issue_exact+=set(g['expected_issue_codes'])==set(row['issue_codes'])
        actual=row['records'].get(row['invoice_id'],{})
        expected=g['records'][row['invoice_id']]
        for k in ('number','date','issuer','recipient','reference','net_cents','tax_cents','total_cents','tax_rate_bps'):
            field_total+=1;field_ok+=k in actual and actual[k]==expected[k]
        clean_ok=not bad and row['status']=='PENDING_APPROVAL' and normalize(row['lines'])==normalize(g['expected_lines'])
        if not bad:
            normal+=1;exact+=clean_ok
        split=by_split.setdefault(g['split'],dict(invoices=0,normal=0,correct_normal_drafts=0))
        split['invoices']+=1;split['normal']+=not bad;split['correct_normal_drafts']+=clean_ok
    ratio=lambda a,b:a/b if b else None
    result=dict(mode=info['mode'],test_double=info['test_double'],invoices=len(rows),
        key_field_accuracy=ratio(field_ok,field_total),clean_journal_exact_accuracy=ratio(exact,normal),
        error_recall=ratio(tp,tp+fn),error_precision=ratio(tp,tp+fp),exact_issue_set_accuracy=ratio(issue_exact,len(rows)),
        true_positives=tp,false_positives=fp,false_negatives=fn,by_split=by_split,
        investigator_cases=sum(r['agent_used'] for r in rows),model_calls=info['model_calls'],
        seconds=info['seconds'],model_cost=info['model_cost'],
        note='Synthetic text PDFs only. Null means no denominator. Offline or scripted scores are not live model scores.')
    if info['mode']=='recheck':
        result['source_model_calls']=info.get('source_model_calls',0)
        result['note']='Frozen saved extractions revalidated with revised Python rules; not a fresh model run. Null means no denominator.'
    if len(rows)==100 and len(load(out/'ledger.json'))==70:
        result['full_approved_balance_matches_oracle']=load(out/'reports.json')['balances']==truth['expected_full_approved_balances']
    save(out/'evaluation.json',result)
    print(__import__('json').dumps(result,indent=2))
    return result
