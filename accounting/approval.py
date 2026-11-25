from pathlib import Path
from .core import load,save,digest,balanced
from .documents import Store
from .workflow import Case
from .runner import write_reports

SNAPSHOT_KEYS=('invoice_id','kind','sources','bank_ids','records','lines')

def approve(output,decisions_path,inp=None):
    output=Path(output);info=load(output/'run_info.json');rows=load(output/'cases.json');decisions=load(decisions_path)
    store=Store(inp)
    if store.fingerprint()!=info['input_fingerprint']:
        raise ValueError('Input evidence changed after the run; rerun before approval')
    if type(decisions) is not dict or set(decisions)-{r['invoice_id'] for r in rows}:
        raise ValueError('Invalid or unknown decision IDs')
    if len({r['invoice_id'] for r in rows})!=len(rows):
        raise ValueError('Duplicate result invoice IDs')
    ledger=[];used_bank=set();used_numbers=set()
    for row in rows:
        decision=decisions.get(row['invoice_id'])
        if decision is None:
            continue
        if type(decision) is not dict or set(decision)!={'decision','snapshot_hash'} or decision['decision'] not in ('approve','reject'):
            raise ValueError('Use the review template schema')
        snapshot={k:row[k] for k in SNAPSHOT_KEYS}
        if decision['snapshot_hash']!=digest(snapshot):
            raise ValueError('Decision does not match the saved evidence and draft version')
        if decision['decision']=='reject':
            continue
        if row['status']!='PENDING_APPROVAL' or row['issue_codes'] or not balanced(row['lines']):
            raise ValueError('Only validated pending drafts can be approved')
        validation=row.get('validation') or {}
        if not validation.get('passed') or validation.get('snapshot_hash')!=digest(snapshot):
            raise ValueError('Saved validation is stale')
        # Re-run deterministic controls against the exact reviewed extraction snapshot.
        previous=dict(store.records)
        try:
            store.records.update(row['records'])
            case=Case(store,row['invoice_id']);case.sources=row['sources'];case.bank_ids=row['bank_ids'];case.kind=row['kind']
            if not case.check_case()['passed']:
                raise ValueError('Current deterministic checks reject this draft')
            case.build_draft()
            if case.lines!=row['lines']:
                raise ValueError('Reviewed lines differ from the confirmed policy calculation')
        finally:
            store.records=previous
        number=row['records'][row['invoice_id']]['number']
        if used_bank.intersection(row['bank_ids']) or number in used_numbers:
            raise ValueError('Approved entries would reuse a bank payment or invoice')
        used_bank.update(row['bank_ids']);used_numbers.add(number)
        ledger.append(dict(invoice_id=row['invoice_id'],invoice_number=number,lines=row['lines'],
                           sources=row['sources'],bank_ids=row['bank_ids'],approval_mode='manual_decision_file',
                           snapshot_hash=decision['snapshot_hash']))
    write_reports(output,store.config,ledger)
    save(output/'approval_decisions.json',decisions)
    print(f'Approved={len(ledger)}. Reports refreshed without any API call.')
    return ledger
