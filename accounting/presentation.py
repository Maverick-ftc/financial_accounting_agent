"""Readable statements in PDF, HTML and CNY-valued CSV, derived from approved reports."""
from decimal import Decimal
from pathlib import Path
from html import escape
from .core import csv_write

def money(cents,grouped=True):
    return format(Decimal(cents)/Decimal(100),',.2f' if grouped else '.2f')

def statement_rows(report):
    if report.get('unit')!='CNY cents' or not all(report['checks'].values()):
        raise ValueError('Only reconciled integer-cent reports can be displayed')
    b=report['balances'];bs=report['balance_sheet'];inc=report['income_statement']
    if b['1002']+b['222101']!=bs['assets_cents'] or -b['222102']!=bs['liabilities_cents']:
        raise ValueError('Balance sheet detail does not match totals')
    if -b['4001']+inc['profit_cents']!=bs['equity_cents'] or bs['assets_cents']!=bs['liabilities_cents']+bs['equity_cents']:
        raise ValueError('Equity reconciliation failed')
    if b['660201']+b['660202']!=inc['expense_cents'] or inc['revenue_cents']-inc['expense_cents']!=inc['profit_cents']:
        raise ValueError('Income statement detail does not reconcile')
    balance=[('Assets','Bank',b['1002']),('Assets','Demo input tax',b['222101']),
        ('Assets','Total assets',bs['assets_cents']),('Liabilities','Demo output tax',bs['liabilities_cents']),
        ('Liabilities','Total liabilities',bs['liabilities_cents']),('Equity','Opening equity',-b['4001']),
        ('Equity','Current-period profit / (loss)',inc['profit_cents']),('Equity','Total equity',bs['equity_cents']),
        ('Total','Total liabilities and equity',bs['liabilities_cents']+bs['equity_cents'])]
    income=[('Revenue','Service revenue',inc['revenue_cents']),
        ('Expenses','Office consumables expense',b['660201']),
        ('Expenses','Employee reimbursement expense',b['660202']),
        ('Expenses','Total expenses',inc['expense_cents']),('Result','Net profit / (loss)',inc['profit_cents'])]
    return balance,income

def export_statements(output,report,entity='Synthetic Business'):
    output=Path(output);output.mkdir(parents=True,exist_ok=True)
    balance,income=statement_rows(report)
    for name,rows in [('balance_sheet',balance),('income_statement',income)]:
        csv_write(output/(name+'.csv'),[dict(section=s,line_item=n,amount_cny=money(v,False)) for s,n,v in rows],
            ['section','line_item','amount_cny'])
    notice=(f'Approved ledger entries: {report["approved_count"]}. Drafts and unresolved cases are excluded.'
            if report['approved_count'] else 'No approved entries. Statements contain opening balances only; unapproved drafts are excluded.')
    note='Educational synthetic data. Simplified project policy, not a statutory financial statement. Demo tax balances are shown separately.'
    def html_table(rows):
        return '<table><thead><tr><th>Section</th><th>Line item</th><th>Amount (CNY)</th></tr></thead><tbody>'+''.join(
            '<tr class="'+('total' if n.startswith('Total') or s=='Result' else '')+'"><td>'+escape(s)+'</td><td>'+escape(n)+
            '</td><td class="number">'+money(v)+'</td></tr>' for s,n,v in rows)+'</tbody></table>'
    document='''<!doctype html><html lang="en"><head><meta charset="utf-8"><title>Financial Statements</title>
<style>body{font-family:"Times New Roman",Times,serif;color:#183247;max-width:960px;margin:40px auto;padding:0 24px;line-height:1.5}
h1{font-size:32px}h2{border-bottom:2px solid #28566d;padding-bottom:8px;margin-top:36px}table{width:100%;border-collapse:collapse}
th,td{padding:11px 12px;border-bottom:1px solid #cedbe2;text-align:left}th{background:#edf3f6}.number{text-align:right}
.total{font-weight:bold;background:#f6f8fa}.notice{padding:16px;background:#eef4f6}.note{font-size:14px;color:#526878}
@media print{body{margin:0;max-width:none}h2{break-before:page}h2:first-of-type{break-before:auto}table{break-inside:avoid}}</style></head><body>'''
    document+='<h1>Financial Statements</h1><p>'+escape(entity)+' | Period: '+escape(report['period'])+' | Unit: CNY</p>'
    document+='<p class="notice">'+escape(notice)+'</p><h2>Balance Sheet</h2>'+html_table(balance)
    document+='<h2>Income Statement</h2>'+html_table(income)+'<p class="note">'+escape(note)+'</p></body></html>'
    (output/'financial_statements.html').write_text(document,encoding='utf-8')
    _pdf(output/'financial_statements.pdf',entity,report['period'],notice,note,balance,income)
    return [output/n for n in ['financial_statements.pdf','financial_statements.html','balance_sheet.csv','income_statement.csv']]

def _pdf(path,entity,period,notice,note,balance,income):
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    from reportlab.platypus import SimpleDocTemplate,Paragraph,Table,TableStyle,Spacer,PageBreak
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib import colors
    regular=Path('C:/Windows/Fonts/times.ttf');bold=Path('C:/Windows/Fonts/timesbd.ttf')
    if regular.exists() and bold.exists():
        pdfmetrics.registerFont(TTFont('StatementTNR',str(regular)))
        pdfmetrics.registerFont(TTFont('StatementTNR-Bold',str(bold)))
        normal,heading='StatementTNR','StatementTNR-Bold'
    else:
        normal,heading='Times-Roman','Times-Bold'
    styles={n:ParagraphStyle(n,fontName=f,fontSize=s,leading=s*1.4,spaceAfter=8)
            for n,f,s in [('title',heading,23),('body',normal,11),('small',normal,9),('head',heading,11)]}
    def p(t,kind='body'):
        return Paragraph(escape(str(t)),styles[kind])
    story=[]
    for index,(title,rows) in enumerate([('Balance Sheet',balance),('Income Statement',income)]):
        if index:story.append(PageBreak())
        story.extend([p(title,'title'),p(entity),p(f'Period: {period} | Unit: CNY'),Spacer(1,8),p(notice,'small'),Spacer(1,12)])
        cells=[[p('Section','head'),p('Line item','head'),p('Amount (CNY)','head')]]
        for section,name,value in rows:
            cells.append([p(section),p(name),p(money(value))])
        t=Table(cells,colWidths=[94,284,137],repeatRows=1)
        commands=[('BACKGROUND',(0,0),(-1,0),colors.HexColor('#edf3f6')),
            ('LINEBELOW',(0,0),(-1,-1),.4,colors.HexColor('#cedbe2')),('VALIGN',(0,0),(-1,-1),'TOP'),
            ('LEFTPADDING',(0,0),(-1,-1),9),('RIGHTPADDING',(0,0),(-1,-1),9),
            ('TOPPADDING',(0,0),(-1,-1),9),('BOTTOMPADDING',(0,0),(-1,-1),9)]
        for i,(section,name,_) in enumerate(rows,1):
            if name.startswith('Total') or section=='Result':
                commands.append(('BACKGROUND',(0,i),(-1,i),colors.HexColor('#f5f8fa')))
        t.setStyle(TableStyle(commands));story.extend([t,Spacer(1,18),p(note,'small')])
    def footer(c,doc):
        c.setFont(normal,8);c.drawString(40,26,'SYNTHETIC PROJECT RESULTS - APPROVED LOCAL LEDGER ONLY')
        c.drawRightString(555,26,str(doc.page))
    SimpleDocTemplate(str(path),pagesize=(595.28,841.89),leftMargin=40,rightMargin=40,topMargin=42,bottomMargin=50,
        title='Financial Statements',author='Financial Accounting Agent').build(story,onFirstPage=footer,onLaterPages=footer)
