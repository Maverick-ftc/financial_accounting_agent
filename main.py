"""One CLI for offline processing, live hybrid processing, approval and evaluation."""
import argparse
import json
import os
import sys
from pathlib import Path
from accounting.core import ROOT
from accounting.settings import load_env

def main():
    ap=argparse.ArgumentParser(description=__doc__);sub=ap.add_subparsers(dest='command',required=True)
    doctor=sub.add_parser('doctor',help='Check installation and configuration; no API call unless requested')
    doctor.add_argument('--check-api',action='store_true')
    run=sub.add_parser('run',help='Process the bundled English complex dataset')
    run.add_argument('--mode',choices=['offline','hybrid'],default='offline')
    run.add_argument('--limit',type=int,default=6)
    run.add_argument('--out',type=Path)
    run.add_argument('--max-calls',type=int,default=100)
    run.add_argument('--max-steps',type=int,default=18)
    run.add_argument('--invoices',help='Optional comma-separated document IDs from data/input/document_index.json')
    ev=sub.add_parser('evaluate',help='Compare a saved run against isolated benchmark answers')
    ev.add_argument('--results',type=Path,required=True)
    approve=sub.add_parser('approve',help='Apply a complete human decision snapshot without calling AI')
    approve.add_argument('--results',type=Path,required=True)
    approve.add_argument('--decisions',type=Path,required=True)
    recheck=sub.add_parser('recheck',help='Revalidate frozen extractions with corrected rules; no API calls')
    recheck.add_argument('--results',type=Path,required=True)
    recheck.add_argument('--out',type=Path,required=True)
    summary=sub.add_parser('summary',help='Print saved draft states and report totals; no API calls')
    summary.add_argument('--results',type=Path,required=True)
    export=sub.add_parser('export',help='Export readable balance sheet and income statement from saved approved reports; no API calls')
    export.add_argument('--results',type=Path,required=True)
    args=ap.parse_args()
    try:
        load_env()
        if args.command=='doctor':
            import pypdf,reportlab
            from accounting.documents import Store
            store=Store()
            result=dict(python=sys.version.split()[0],pypdf=pypdf.__version__,reportlab=reportlab.Version,
                documents=len(store.docs),invoices=len(store.invoices),bank_rows=len(store.bank),
                api_key_configured=bool(os.environ.get('DEEPSEEK_API_KEY')),
                model=os.environ.get('DEEPSEEK_MODEL','deepseek-flash'),live_api_checked=False)
            if args.check_api:
                from accounting.deepseek import DeepSeekClient
                client=DeepSeekClient(max_calls=1)
                reply=client.json_object('Reply in English JSON: {"ok":true}.',{'purpose':'Connection test'},role='connection_test')
                if reply.get('ok') is not True:
                    raise ValueError('Unexpected API connection-test response')
                result.update(live_api_checked=True,usage=client.usage)
            print(json.dumps(result,indent=2))
        elif args.command=='run':
            from accounting.runner import run as execute
            execute(args.mode,args.limit,args.out,args.max_calls,args.max_steps,
                    invoice_ids=args.invoices.split(',') if args.invoices else None)
        elif args.command=='evaluate':
            from accounting.evaluation import evaluate
            evaluate(args.results)
        elif args.command=='approve':
            from accounting.approval import approve as execute
            execute(args.results,args.decisions)
        elif args.command=='recheck':
            from accounting.recheck import recheck as execute
            execute(args.results,args.out)
        elif args.command=='summary':
            from accounting.summary import show
            show(args.results)
        else:
            from accounting.core import load
            from accounting.presentation import export_statements
            files=export_statements(args.results,load(args.results/'reports.json'),load(ROOT/'data/input/config.json')['entity'])
            for file in files:
                print(file.resolve())
    except (ValueError,OSError,RuntimeError) as exc:
        ap.exit(2,f'Error: {exc}\n')

if __name__=='__main__':
    main()
