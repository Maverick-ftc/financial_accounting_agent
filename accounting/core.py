import csv
import hashlib
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
ACCOUNTS={'1002':'Bank','222101':'Demo input tax','222102':'Demo output tax',
          '4001':'Opening equity','6001':'Service revenue','660201':'Office consumables expense',
          '660202':'Employee reimbursement expense'}

def load(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))

def save(path,value):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(value,ensure_ascii=True,indent=2),encoding='utf-8')

def csv_write(path,rows,fields):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('w',encoding='utf-8-sig',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=fields);writer.writeheader();writer.writerows(rows)

def digest(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,ensure_ascii=True).encode()).hexdigest()

def balanced(lines):
    return bool(lines) and all(type(x) is dict and set(x)=={'account','debit','credit'}
        and x['account'] in ACCOUNTS and type(x['debit']) is int and type(x['credit']) is int
        and x['debit']>=0 and x['credit']>=0 and ((x['debit']>0)!=(x['credit']>0)) for x in lines
        ) and sum(x['debit']-x['credit'] for x in lines)==0

def make_journal(kind,invoice):
    n,t,g=invoice['net_cents'],invoice['tax_cents'],invoice['total_cents']
    if kind=='revenue':
        pairs=[('1002',g),('6001',-n),('222102',-t)]
    elif kind=='purchase':
        pairs=[('660201',n),('222101',t),('1002',-g)]
    elif kind=='reimbursement':
        pairs=[('660202',g),('1002',-g)]
    else:
        raise ValueError('Unconfirmed business classification')
    lines=[dict(account=a,debit=max(v,0),credit=max(-v,0)) for a,v in pairs if v]
    if not balanced(lines):
        raise ValueError('Draft does not balance')
    return lines

def reports(config,ledger):
    opening=config['opening_balances']
    if set(opening)-set(ACCOUNTS) or any(type(x) is not int for x in opening.values()) or sum(opening.values()):
        raise ValueError('Invalid opening balances')
    debits={a:0 for a in ACCOUNTS};credits=dict(debits)
    ids=set()
    for row in ledger:
        if row['invoice_id'] in ids or not balanced(row['lines']):
            raise ValueError('Duplicate or invalid approved entry')
        ids.add(row['invoice_id'])
        for line in row['lines']:
            debits[line['account']]+=line['debit'];credits[line['account']]+=line['credit']
    balances={a:opening.get(a,0)+debits[a]-credits[a] for a in ACCOUNTS}
    revenue=-balances['6001'];expense=balances['660201']+balances['660202'];profit=revenue-expense
    assets=balances['1002']+balances['222101'];liabilities=-balances['222102'];equity=-balances['4001']+profit
    checks=dict(debits_equal_credits=sum(debits.values())==sum(credits.values()),
                trial_balance_zero=sum(balances.values())==0,balance_sheet_balances=assets==liabilities+equity)
    if not all(checks.values()):
        raise ValueError('Report control failed')
    return dict(period=config['period'],unit='CNY cents',approved_count=len(ledger),balances=balances,
        trial_balance=[dict(account=a,name=ACCOUNTS[a],opening_cents=opening.get(a,0),debit_cents=debits[a],
                            credit_cents=credits[a],closing_cents=balances[a]) for a in ACCOUNTS],
        income_statement=dict(revenue_cents=revenue,expense_cents=expense,profit_cents=profit),
        balance_sheet=dict(assets_cents=assets,liabilities_cents=liabilities,equity_cents=equity),checks=checks)
