"""Print a readable saved-run overview without calling models or changing files."""
from pathlib import Path
from .core import load

def show(output):
    output=Path(output);rows=load(output/'cases.json');info=load(output/'run_info.json');report=load(output/'reports.json')
    print(f'Run folder: {output.resolve()}')
    print(f'Mode: {info["mode"]}; model requests in this run: {info["model_calls"]}')
    if 'source_model_calls' in info:
        print(f'Model requests in original source run: {info["source_model_calls"]}')
    print(f'{"Invoice":<16} {"Business":<15} {"Status":<19} {"Gross CNY":>12}')
    for row in rows:
        gross=row['records'].get(row['invoice_id'],{}).get('total_cents')
        amount=f'{gross/100:,.2f}' if type(gross) is int else 'unknown'
        print(f'{row["invoice_id"]:<16} {(row["kind"] or "unconfirmed"):<15} {row["status"]:<19} {amount:>12}')
        if row['issue_codes']:
            print('  Issues: '+', '.join(row['issue_codes']))
        for question in row['questions']:
            print('  Question: '+question)
    print(f'Approved ledger entries: {report["approved_count"]}')
    print(f'Reported revenue CNY: {report["income_statement"]["revenue_cents"]/100:,.2f}')
    print(f'Reported expenses CNY: {report["income_statement"]["expense_cents"]/100:,.2f}')
    print(f'Reported profit CNY: {report["income_statement"]["profit_cents"]/100:,.2f}')
    if not report['approved_count']:
        print('Reports contain opening balances only. Drafts require explicit human approval before posting.')
    print('Draft evidence: cases.json; approval template: review_template.json; full actions: trace.jsonl')
    print('Balance sheet: financial_statements.pdf page 1; income statement: page 2.')
    print('Browser view: financial_statements.html; Excel views: balance_sheet.csv and income_statement.csv (CNY).')
