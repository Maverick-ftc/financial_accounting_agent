import json
import time
from pathlib import Path
from .core import ROOT,save,csv_write,digest,reports
from .documents import Store
from .extraction import extract
from .deepseek import DeepSeekClient,APIError,CallBudget
from .workflow import Case,TERMINAL_SOURCE_ERRORS

QUESTIONS={
    'DUPLICATE_DOCUMENT':'Please confirm whether this is a duplicate submission of an existing invoice.',
    'MISSING_INVOICE_NUMBER':'Please supply the complete original invoice including its number.',
    'MISSING_RECEIPT':'Please supply the employee personal-payment receipt.',
    'MISSING_ACCEPTANCE':'Please supply client acceptance or delivery confirmation for the service.',
    'MISSING_CLAIM':'Please supply the expense claim and employee identity.',
    'PAYMENT_MISMATCH':'Please explain the payment difference and supply any additional settlement evidence.',
    'CONTRACT_INVOICE_MISMATCH':'Please confirm the agreed contract price and supply any written amendment.',
    'UNPARSED_EVIDENCE':'Please extract or manually review the unsupported source documents.',
    'UNCERTAIN_CLASSIFICATION':'Please confirm the business purpose and applicable company policy.',
}

def write_reports(out,config,ledger):
    result=reports(config,ledger)
    save(out/'ledger.json',ledger);save(out/'reports.json',result)
    csv_write(out/'trial_balance.csv',result['trial_balance'],
        ['account','name','opening_cents','debit_cents','credit_cents','closing_cents'])
    csv_write(out/'journal.csv',[dict(invoice_id=row['invoice_id'],**line) for row in ledger for line in row['lines']],
        ['invoice_id','account','debit','credit'])
    from .presentation import export_statements
    export_statements(out,result,config['entity'])

def run(mode='offline',limit=6,output=None,max_calls=100,max_steps=18,inp=None,client=None,invoice_ids=None):
    if mode not in ('offline','hybrid') or min(limit,max_calls,max_steps)<=0:
        raise ValueError('Invalid mode or limits')
    store=Store(inp)
    selected=list(invoice_ids) if invoice_ids else store.invoices[:limit]
    if not selected or len(selected)!=len(set(selected)) or set(selected)-set(store.invoices):
        raise ValueError('Select distinct indexed invoices')
    out=Path(output or ROOT/'results'/time.strftime('%Y%m%d_%H%M%S'))
    if out.exists() and any(out.iterdir()):
        raise ValueError('Output folder is not empty. Choose a fresh output path.')
    out.mkdir(parents=True,exist_ok=True)
    start=time.perf_counter();attempts={};cases=[];api_failure=None
    def emit(event):
        with (out/'trace.jsonl').open('a',encoding='utf-8') as f:
            f.write(json.dumps(event,ensure_ascii=True)+'\n')
        if event['event'] in ('tool_call','route'):
            print(f'[{event.get("invoice_id","batch")}] {event["event"]}: {event.get("name",event.get("route",""))}',flush=True)
    (out/'trace.jsonl').touch()
    initial_fingerprint=store.fingerprint()
    metadata=dict(mode=mode,selected_invoice_ids=selected,input_fingerprint=initial_fingerprint,
                  model_cost=None,cost_note='Read provider billing; null does not mean zero.',
                  approvals='Explicit human decisions are required; no auto-approval option.')
    def get_client():
        nonlocal client
        if mode!='hybrid':
            raise ValueError('Offline mode never calls AI')
        if api_failure:
            raise APIError(api_failure)
        if client is None:
            client=DeepSeekClient(max_calls=max_calls)
        return client
    try:
        for did in selected:
            case=Case(store,did,emit=emit,attempts=attempts)
            route='python_fast_path'
            try:
                check=case.check_case()
                if set(check['issue_codes'])&TERMINAL_SOURCE_ERRORS:
                    route='python_block'
                elif did not in store.records and mode=='hybrid':
                    route='ai_extraction';case.client=get_client()
                    for retry in range(3):
                        try:
                            extract(store,did,case.client,emit,attempts);break
                        except ValueError as exc:
                            emit(dict(event='extraction_failed',invoice_id=did,attempt=retry+1,error=str(exc)))
                            if retry==2:
                                raise
                    check=case.check_case()
                if check['passed']:
                    case.build_draft();case.finish_case('ready','Evidence and bookkeeping controls passed.',[])
                elif route=='python_block':
                    case.finish_case('review','A deterministic source control blocked this invoice.',
                        [QUESTIONS.get(x,'Please resolve '+x+'.') for x in check['issue_codes'] if x in TERMINAL_SOURCE_ERRORS])
                elif mode=='offline':
                    route='offline_review'
                    case.finish_case('review','Offline mode leaves unsupported or unresolved evidence for human review.',
                        [QUESTIONS.get(x,'Please resolve '+x+'.') for x in check['issue_codes']])
                elif 'UNPARSED_EVIDENCE' not in check['issue_codes'] and set(check['issue_codes'])&{
                        'MISSING_RECEIPT','MISSING_ACCEPTANCE','MISSING_CLAIM','MISSING_CONTRACT','MISSING_DELIVERY_CONFIRMATION'}:
                    route='python_missing_evidence'
                    case.finish_case('review','Required evidence is absent; no model call is needed to request it.',
                        [QUESTIONS.get(x,'Please resolve '+x+'.') for x in check['issue_codes']])
                else:
                    route='agent_investigation';case.client=get_client();case.investigate(max_steps)
            except (APIError,CallBudget) as exc:
                api_failure=str(exc);route='api_unavailable'
                emit(dict(event='api_unavailable',invoice_id=did,error=str(exc)))
                case.finish_case('review','AI processing is unavailable: '+str(exc),
                    ['Please check local API configuration, account balance, network or call budget, then rerun.'])
                case.result['issue_codes']=sorted(set(case.result['issue_codes']+['API_UNAVAILABLE']))
            except (ValueError,TypeError,KeyError) as exc:
                route='processing_review'
                emit(dict(event='processing_error',invoice_id=did,error=str(exc)))
                case.finish_case('review','Processing needs human review: '+str(exc),
                    ['Please inspect the extraction, source evidence and trace before approval.'])
                case.result['issue_codes']=sorted(set(case.result['issue_codes']+['PROCESSING_ERROR']))
            case.result['route']=route
            cases.append(case.result)
            emit(dict(event='route',invoice_id=did,route=route,status=case.result['status']))
            save(out/'cases.json',cases)
    finally:
        metadata.update(seconds=round(time.perf_counter()-start,3),completed_invoices=len(cases),
            model_calls=getattr(client,'calls',0),model=getattr(client,'model',None),
            usage=getattr(client,'usage',[]),live_api_verified=bool(client and getattr(client,'usage',[]) and not getattr(client,'is_test_double',False)),
            test_double=bool(getattr(client,'is_test_double',False)))
        if not metadata['model_calls']:
            metadata['model_cost']=0
        save(out/'run_info.json',metadata)
    save(out/'extractions.json',{did:dict(record=r,origin=store.origins[did]) for did,r in store.records.items()})
    save(out/'review_template.json',{r['invoice_id']:dict(decision='reject',snapshot_hash=digest({k:r[k] for k in
        ('invoice_id','kind','sources','bank_ids','records','lines')})) for r in cases if r['status']=='PENDING_APPROVAL'})
    csv_write(out/'review_queue.csv',[dict(invoice_id=r['invoice_id'],status=r['status'],route=r['route'],
        issues=';'.join(r['issue_codes']),questions=';'.join(r['questions'])) for r in cases],
        ['invoice_id','status','route','issues','questions'])
    write_reports(out,store.config,[])
    print(f'Invoices={len(cases)}, pending={sum(r["status"]=="PENDING_APPROVAL" for r in cases)}, '
          f'review={sum(r["status"]=="REVIEW_REQUIRED" for r in cases)}, model_calls={metadata["model_calls"]}')
    print(f'Results: {out.resolve()}')
    return out
