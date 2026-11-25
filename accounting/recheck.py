"""Revalidate saved extractions under current controls, without another API call."""
import json
from pathlib import Path
from .core import ROOT,load,save,csv_write,digest
from .documents import Store,FIELDS
from .workflow import Case
from .runner import write_reports,QUESTIONS

def recheck(source,output,inp=None):
    source,output=Path(source),Path(output)
    if output.resolve()==source.resolve() or (output.exists() and any(output.iterdir())):
        raise ValueError('Recheck needs a fresh output folder; preserve the original run')
    info=load(source/'run_info.json');old=load(source/'cases.json');store=Store(inp)
    if store.fingerprint()!=info['input_fingerprint']:
        raise ValueError('Input files changed since the saved run; do a fresh run instead')
    ids=[r['invoice_id'] for r in old]
    if len(ids)!=len(set(ids)) or set(ids)!=set(info['selected_invoice_ids']) or set(ids)-set(store.invoices):
        raise ValueError('Saved run is incomplete or has unknown invoices')
    # Validate the saved extraction schema. Known-template facts remain authoritative.
    for row in old:
        for did,record in row['records'].items():
            if did not in store.docs or set(record)!=set(FIELDS):
                raise ValueError('Saved record is outside the input or has an invalid schema')
            if any(v is not None and type(v) is not FIELDS[k] for k,v in record.items()):
                raise ValueError('Saved extraction has invalid field types')
            if store.origins.get(did)=='python_template':
                if record!=store.records[did]:
                    raise ValueError('Saved values conflict with an authoritative template extraction')
            else:
                store.records[did]=record
                store.origins[did]=row.get('extraction_origins',{}).get(did,'saved_extraction')
    output.mkdir(parents=True,exist_ok=True)
    trace=[];rows=[]
    for oldrow in old:
        case=Case(store,oldrow['invoice_id'],emit=trace.append)
        for did in oldrow['sources']:
            if did!=case.invoice_id and did not in case.sources:
                case.attach_document(did)
        case.select_bank_matches(oldrow['bank_ids']) if oldrow['bank_ids'] else None
        case.kind=oldrow.get('kind')
        checked=case.check_case()
        if checked['passed']:
            case.build_draft()
            case.finish_case('ready','Saved extractions passed the corrected deterministic controls; new human approval is required.',[])
        else:
            case.finish_case('review','Saved extractions still require review under current controls.',
                [QUESTIONS.get(x,'Please resolve '+x+'.') for x in checked['issue_codes']])
        row=case.result
        row.update(route='saved_extraction_recheck',previous_status=oldrow['status'],
                   previous_issue_codes=oldrow['issue_codes'])
        rows.append(row)
        trace.append(dict(event='rechecked',invoice_id=row['invoice_id'],previous_status=oldrow['status'],
                          status=row['status'],issue_codes=row['issue_codes']))
    save(output/'cases.json',rows)
    save(output/'run_info.json',dict(mode='recheck',selected_invoice_ids=ids,input_fingerprint=store.fingerprint(),
        completed_invoices=len(rows),model=info.get('model'),model_calls=0,usage=[],seconds=0,model_cost=0,
        test_double=info.get('test_double',False),live_api_verified=False,
        source_run=str(source),source_model_calls=info.get('model_calls',0),
        note='Reuses frozen saved extractions, not a fresh model evaluation. No API calls or automatic approvals.'))
    with (output/'trace.jsonl').open('w',encoding='utf-8') as f:
        for event in trace:
            f.write(json.dumps(event,ensure_ascii=True)+'\n')
    save(output/'extractions.json',{did:dict(record=r,origin=store.origins[did]) for did,r in store.records.items()})
    keys=('invoice_id','kind','sources','bank_ids','records','lines')
    save(output/'review_template.json',{r['invoice_id']:dict(decision='reject',snapshot_hash=digest({k:r[k] for k in keys}))
        for r in rows if r['status']=='PENDING_APPROVAL'})
    csv_write(output/'review_queue.csv',[dict(invoice_id=r['invoice_id'],status=r['status'],route=r['route'],
        issues=';'.join(r['issue_codes']),questions=';'.join(r['questions'])) for r in rows],
        ['invoice_id','status','route','issues','questions'])
    write_reports(output,store.config,[])
    print(f'Rechecked={len(rows)}, pending={sum(r["status"]=="PENDING_APPROVAL" for r in rows)}, '
          f'review={sum(r["status"]=="REVIEW_REQUIRED" for r in rows)}, new_model_calls=0')
    print(f'Results: {output.resolve()}')
    return output
