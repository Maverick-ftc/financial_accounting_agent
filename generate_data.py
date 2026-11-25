"""Build the complete English synthetic benchmark. No model or API key required."""
import argparse
import hashlib
import random
from collections import Counter
from datetime import datetime,timedelta
from pathlib import Path
from xml.sax.saxutils import escape
from reportlab.lib import colors
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import SimpleDocTemplate,Paragraph,Table,TableStyle,Spacer,PageBreak
from pypdf import PdfReader,PdfWriter
from accounting.core import ROOT,ACCOUNTS,save,csv_write

COMPANY='Clearview Business Services Ltd (TEST)'
SCALAR_KEYS=['type','number','date','issuer','recipient','reference','description','net_cents',
             'tax_cents','total_cents','tax_rate_bps','employee','invoice_reference','completed']
TYPE_TITLES={'invoice':'STANDARD INVOICE','contract':'STANDARD SERVICE AGREEMENT',
             'acceptance':'STANDARD DELIVERY CONFIRMATION','receipt':'STANDARD PAYMENT RECEIPT',
             'claim':'STANDARD EXPENSE CLAIM','order':'STANDARD OFFICE PURCHASE ORDER'}
LABELS={'number':'Document number','date':'Document date','issuer':'Issued by','recipient':'Issued to',
        'reference':'Business reference','description':'Description','net_cents':'Net amount CNY',
        'tax_cents':'Tax amount CNY','total_cents':'Total amount CNY','tax_rate_bps':'Demo rate bps',
        'employee':'Employee','invoice_reference':'Related invoice','completed':'Completion confirmed'}

def money(v):
    return f'{v/100:,.2f}'

def para(text,size=10,font='Helvetica'):
    return Paragraph(escape(str(text)),ParagraphStyle('p',fontName=font,fontSize=size,leading=size*1.45,spaceAfter=9))

def grid(rows,widths):
    result=Table([[para(x,9) for x in row] for row in rows],colWidths=widths,repeatRows=1)
    result.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),colors.HexColor('#edf2f7')),
        ('GRID',(0,0),(-1,-1),.4,colors.HexColor('#bccbd6')),('VALIGN',(0,0),(-1,-1),'TOP'),
        ('LEFTPADDING',(0,0),(-1,-1),8),('RIGHTPADDING',(0,0),(-1,-1),8),
        ('TOPPADDING',(0,0),(-1,-1),6),('BOTTOMPADDING',(0,0),(-1,-1),6)]))
    return result

def footer(c,doc):
    c.setFont('Helvetica',7)
    c.setFillColor(colors.HexColor('#647789'))
    text='SYNTHETIC TEST DATA - NO VALID TRANSACTION' if doc.pagesize[0]<400 else 'SYNTHETIC EDUCATIONAL DATA - NOT A VALID CONTRACT, INVOICE OR RECEIPT'
    c.drawString(30,25,text);c.drawRightString(doc.pagesize[0]-30,25,str(doc.page))

def render(path,record,variant):
    role=record['type'];width=340 if role=='receipt' and variant==1 else 595.28
    height=620 if width==340 else 841.89
    story=[]
    if variant==0:
        story.append(para(TYPE_TITLES[role],18,'Helvetica-Bold'))
        story.append(para('Synthetic evidence copy. All parties and signatures are fictional.',8))
        for key,label in LABELS.items():
            value=record.get(key)
            if value is not None:
                if key.endswith('_cents'):
                    value=money(value)
                elif key=='completed':
                    value='YES' if value else 'NO'
                story.append(para(f'{label}: {value}'))
    elif role=='invoice':
        title='INVOICE / BILLING ADVICE' if variant==1 else 'Invoice - Account Statement'
        story=[para(title,20,'Times-Bold'),para(f'Invoice ID: {record["number"] or "[not supplied]"}'),
            para(f'Dated {record["date"]}. Billed by {record["issuer"]} to {record["recipient"]}.'),
            grid([['Work / goods supplied','Business reference'],[record['description'],record['reference']]],[325,185]),
            grid([['Net (CNY)','Demo rate (bps)','Tax (CNY)','Payable (CNY)'],
                  [money(record['net_cents']),str(record['tax_rate_bps']),money(record['tax_cents']),money(record['total_cents'])]],[130,120,130,130]),
            para('This billing advice does not establish delivery acceptance or receipt of funds.')]
        if variant==2:
            story=[para('Invoice notification letter',20,'Times-Bold'),
                para(f'Invoice reference: {record["number"] or "[not supplied]"}'),
                para(f'On {record["date"]}, {record["issuer"]} billed {record["recipient"]} for {record["description"]}.'),
                para(f'The net charge is CNY {money(record["net_cents"])}. The fictional tax is CNY {money(record["tax_cents"])} '
                     f'at {record["tax_rate_bps"]} basis points. The total is CNY {money(record["total_cents"])}.'),
                para(f'Please quote {record["reference"]} in correspondence. Settlement is recorded separately.')]
    elif role=='contract':
        story=[para('Statement of Work' if variant==1 else 'Project Engagement Letter',21,'Times-Bold'),
            para(f'Agreement reference {record["reference"]}; signed {record["date"]}.'),
            para(f'Client: {record["recipient"]}'),para(f'Service provider: {record["issuer"]}'),
            para('1. Scope and deliverables',13,'Helvetica-Bold'),
            para(f'The provider will perform {record["description"]}. Deliverables include an analysis report, supporting '
                 'working papers and a handover meeting. No software licence or physical equipment is transferred.'),
            para('2. Service window and evidence of completion',13,'Helvetica-Bold'),
            para('Work is scheduled for 1-25 October 2026. Completion requires a separate client email or signed '
                 'delivery confirmation. An invoice or bank receipt alone is not proof of acceptance under this test policy.'),
            para('3. Price and payment',13,'Helvetica-Bold'),
            para(f'The total agreed price, including the fictional demo tax, is CNY {money(record["total_cents"])}. '
                 'Payment may be split into 40 percent at commencement and the remaining balance after acceptance. '
                 f'The payment memo must quote {record["reference"]}.'),PageBreak(),
            para('Schedule: responsibilities and amendments',18,'Times-Bold'),
            para('The client supplies source information and names an acceptance contact. Scope or price changes '
                 'require a written amendment confirmed by both parties. A later invoice alone does not amend this agreement.'),
            para('The parties retain records of delivery, acceptance and settlement. If documents conflict, they '
                 'will check the underlying agreement and correspondence before authorising accounting treatment.'),
            para('Confidentiality and dispute handling',13,'Helvetica-Bold'),
            para('Information is used solely for this engagement. Any service or payment dispute is first raised '
                 'with the project contacts. Uncompleted work and any proposed cancellation settlement require separate confirmation.'),
            grid([['Client representative','Provider representative'],['TEST ACKNOWLEDGEMENT','TEST ACKNOWLEDGEMENT']],[255,255])]
    elif role=='receipt':
        if variant==1:
            story=[para('PAYMENT SLIP',17,'Courier-Bold'),para(record['issuer'],11,'Courier'),
                para(f'Receipt {record["number"]}'),para(f'Date {record["date"]}'),
                grid([['Item','CNY'],['Client meeting meal',money(record['total_cents'])],['PAID',money(record['total_cents'])]],[155,105]),
                para(f'Paid personally by {record["employee"]}.'),para(f'Invoice ID: {record["invoice_reference"]}'),
                para(f'Reference {record["reference"]}'),para('This slip is not an employer reimbursement record.',8)]
        else:
            story=[para('Merchant Payment Confirmation',20,'Times-Bold'),
                para(f'{record["issuer"]} confirms receipt of CNY {money(record["total_cents"])} '
                     f'from {record["employee"]} on {record["date"]} for a client meeting meal.'),
                para(f'Payment reference {record["reference"]}. Receipt identifier {record["number"]}.'),
                para(f'Related invoice: {record["invoice_reference"]}.'),
                para('The employee used personal funds. This record does not establish repayment by the employer.')]
    elif role=='acceptance':
        story=[para('Client Acceptance Email' if variant==1 else 'Service Delivery Acknowledgement',19,'Times-Bold'),
            para(f'From: {record["issuer"]}'),para(f'To: {record["recipient"]}'),para(f'Date: {record["date"]}'),
            para(f'Re: {record["reference"]} - {record["description"]}'),
            para('We confirm that the agreed report and handover materials have been received and accepted on '
                 '26 October 2026. There are no outstanding deliverables for this engagement.'),
            para(f'The confirmed total is CNY {money(record["total_cents"])}. Please check payment separately.')]
    elif role=='order':
        story=[para('Office Supplies Order and Delivery Note',18,'Times-Bold'),
            para(f'Buyer {record["recipient"]} ordered from {record["issuer"]} on {record["date"]}.'),
            para(f'Order reference {record["reference"]}. Total CNY {money(record["total_cents"])}.'),
            para('The paper and binding consumables were received and put into office use on 26 October 2026. '
                 'No resale inventory or capital equipment is included. The test coordinator confirmed receipt.'),
            para('Payment is due in one bank transfer. Match the order reference and vendor identity before settlement.')]
    elif role=='claim':
        story=[para('Employee Expense Application',20,'Times-Bold'),
            para(f'Employee {record["employee"]} requests reimbursement of CNY {money(record["total_cents"])} '
                 f'for a client project meeting meal. Application date {record["date"]}.'),
            para(f'The merchant is {record["issuer"]}. Invoice {record["invoice_reference"]}; '
                 f'expense reference {record["reference"]}.'),
            para('The employee paid personally. Please review both the invoice and personal payment receipt, '
                 'then reimburse the employee. The department test reviewer confirmed the business purpose.'),
            para('This application does not prove that the company has already paid the employee.')]
    if role=='contract' and variant==0:
        story += [para('Scope, acceptance and payment controls',13,'Helvetica-Bold'),
            para('Service is scheduled for 1-25 October 2026. Deliver a report and working papers. A separate '
                 'client acceptance is required. Payments may be split 40/60; receipt of funds does not replace acceptance.'),
            para('Changes must be recorded in a written amendment. The parties preserve delivery and settlement '
                 'records and resolve discrepancies before authorising a journal. TEST signatures have no real legal effect.')]
    if role=='order' and variant==0:
        story.append(para('Paper and binding supplies were received and consumed in the office this month. No inventory or fixed assets are included.'))
    if role=='claim' and variant==0:
        story.append(para('Review the merchant invoice and personal payment evidence. Company bank payments must be made to the employee.'))
    SimpleDocTemplate(str(path),pagesize=(width,height),leftMargin=40 if width>400 else 30,
        rightMargin=40 if width>400 else 30,topMargin=35,bottomMargin=55,
        title='Synthetic accounting evidence',author='Financial Accounting Agent Demo').build(story,onFirstPage=footer,onLaterPages=footer)

def generate(output=ROOT/'data',seed=566026):
    output=Path(output)
    if (output/'input/document_index.json').exists():
        raise ValueError('Dataset already exists. Use --output with a fresh folder.')
    inbox=output/'input/inbox';inbox.mkdir(parents=True,exist_ok=True)
    rng=random.Random(seed);documents=[];answers=[];bank=[];samples={};used=set();count=0
    def add(record,variant):
        nonlocal count
        count+=1
        did=f'DOC-{rng.randrange(10000000,99999999)}'
        while did in used:
            did=f'DOC-{rng.randrange(10000000,99999999)}'
        used.add(did);path=inbox/f'{did}.pdf';render(path,record,variant)
        documents.append(dict(document_id=did,path=f'inbox/{did}.pdf',
            received_at=(datetime(2026,10,30)+timedelta(seconds=count)).isoformat(),
            sha256=hashlib.sha256(path.read_bytes()).hexdigest()))
        samples.setdefault((record['type'],variant),path)
        return did
    def rec(role,d,**kwargs):
        r={k:None for k in SCALAR_KEYS}
        r.update(type=role,date=d['date'],issuer=d['seller'],recipient=d['buyer'],reference=d['reference'],
                 description=d['description'],total_cents=d['total_cents'])
        r.update(kwargs);return r
    issues=['DUPLICATE_DOCUMENT','PAYMENT_MISMATCH','MISSING_RECEIPT','MISSING_ACCEPTANCE',
            'CONTRACT_INVOICE_MISMATCH','MISSING_INVOICE_NUMBER']
    first=None
    for i in range(1,101):
        issue=None if i<=70 else issues[(i-71)//5]
        kind=['revenue','purchase','reimbursement'][(i-1)%3]
        if issue in ('DUPLICATE_DOCUMENT','MISSING_ACCEPTANCE','CONTRACT_INVOICE_MISMATCH'):
            kind='revenue'
        if issue=='MISSING_RECEIPT':
            kind='reimbursement'
        vendor=f'{["Northside Office","Paperbridge Supplies","Brightleaf Stationery"][i%3]} {i:03d} (TEST)'
        if kind=='reimbursement':
            vendor=f'{["Meadow Cafe","Riverside Dining","Oak Kitchen"][(i//3)%3]} {i:03d} (TEST)'
        client=f'{["Linden","Orion","Maple","Cedar","Harbor"][i%5]} Technology {i:03d} Ltd (TEST)'
        n=rng.randint(35000,450000);rate=600 if kind=='revenue' else 1300 if kind=='purchase' else 0
        tax=(n*rate+5000)//10000
        d=dict(kind=kind,date=f'2026-10-{1+(i-1)%25:02d}',number=f'TEST-INV-{800000+i}',
            reference=f'REF-{20261000+i}',seller=COMPANY if kind=='revenue' else vendor,
            buyer=client if kind=='revenue' else COMPANY,employee=f'Employee {i:03d} (TEST)',
            description='Business workflow review service' if kind=='revenue' else
                        'Office paper and binding consumables' if kind=='purchase' else 'Client meeting meal',
            net_cents=n,tax_cents=tax,total_cents=n+tax,tax_rate_bps=rate)
        if issue=='DUPLICATE_DOCUMENT':
            d=dict(first)
        if first is None:
            first=dict(d)
        variant=((i-1)//3)%3
        if issue=='DUPLICATE_DOCUMENT':
            variant=0
        inv=rec('invoice',d,number=None if issue=='MISSING_INVOICE_NUMBER' else d['number'],
            net_cents=d['net_cents'],tax_cents=d['tax_cents'],tax_rate_bps=d['tax_rate_bps'])
        invoice_id=add(inv,variant);ids=[invoice_id];records={invoice_id:inv}
        def support(r):
            sid=add(r,variant);ids.append(sid);records[sid]=r
        if kind=='revenue':
            support(rec('contract',d,number=None,
                total_cents=d['total_cents']+(20000 if issue=='CONTRACT_INVOICE_MISMATCH' else 0)))
            if issue!='MISSING_ACCEPTANCE':
                support(rec('acceptance',d,number=None,date='2026-10-26',issuer=d['buyer'],recipient=COMPANY,completed=True))
        elif kind=='purchase':
            support(rec('order',d,number=None,completed=True))
        else:
            if issue!='MISSING_RECEIPT':
                support(rec('receipt',d,number=f'PAY-{i:05d}',recipient=None,employee=d['employee'],invoice_reference=d['number']))
            support(rec('claim',d,number=None,recipient=None,date='2026-10-27',employee=d['employee'],invoice_reference=d['number']))
        bids=[]
        if issue!='DUPLICATE_DOCUMENT':
            paid=d['total_cents']+(1000 if issue=='PAYMENT_MISMATCH' else 0)
            parts=[paid*40//100,paid-paid*40//100] if kind=='revenue' and i<=70 and i%4==0 else [paid]
            for j,amount in enumerate(parts):
                bid=f'TX-{len(bank)+1:05d}';bids.append(bid)
                party=d['buyer'] if kind=='revenue' else d['employee'] if kind=='reimbursement' else d['seller']
                bank.append(dict(bank_id=bid,date=f'2026-10-{27+j:02d}',counterparty=party,currency='CNY',
                    signed_amount_cents=amount if kind=='revenue' else -amount,
                    memo=f'{d["reference"]} settlement part {j+1}'))
        # Independent oracle; never calls runtime make_journal.
        n,t,g=d['net_cents'],d['tax_cents'],d['total_cents']
        tuples=[('1002',g,0),('6001',0,n),('222102',0,t)] if kind=='revenue' else \
               [('660201',n,0),('222101',t,0),('1002',0,g)] if kind=='purchase' else \
               [('660202',g,0),('1002',0,g)]
        lines=[dict(account=a,debit=dr,credit=cr) for a,dr,cr in tuples if dr or cr]
        answers.append(dict(case_id=f'C{i:03d}',invoice_id=invoice_id,kind=kind,document_ids=ids,
            bank_ids=bids,records=records,expected_issue_codes=[issue] if issue else [],
            expected_action='REVIEW_REQUIRED' if issue else 'PENDING_APPROVAL',
            expected_lines=[] if issue else lines,layout_variant=variant,
            split='known_template' if variant==0 else 'development' if variant==1 else 'heldout_template'))
    rng.shuffle(documents);rng.shuffle(bank)
    save(output/'input/document_index.json',documents)
    csv_write(output/'input/bank_statement.csv',bank,
              ['bank_id','date','counterparty','currency','signed_amount_cents','memo'])
    config=dict(entity=COMPANY,period='2026-10',currency='CNY',accounts=ACCOUNTS,
        opening_balances={'1002':10000000,'4001':-10000000},
        assumptions=['Synthetic demo rates only; no tax eligibility determination.',
                     'Normal cases are completed, approved as business expenses and fully settled within the month.',
                     'No inventory, capital assets, accruals, prepayments or tax filing in this MVP.'])
    save(output/'input/config.json',config)
    (output/'input/company_policy.txt').write_text('''EDUCATIONAL BOOKKEEPING POLICY\nCurrency: CNY. Monetary values are integer cents in structured records.\nService revenue requires a contract AND separate client acceptance for this benchmark.\nSplit service payments can be combined when the business reference and counterparty agree.\nOffice consumables require a delivery-confirmed purchase order; these are current office expenses.\nEmployee reimbursement requires invoice, merchant personal-payment receipt and expense claim.\nThe company pays the employee, not the merchant, in reimbursement cases.\nRevenue: debit 1002 gross; credit 6001 net and 222102 demo tax.\nPurchases: debit 660201 net and 222101 demo tax; credit 1002 gross.\nReimbursements: debit 660202 gross; credit 1002 gross. No input-tax deduction in this demo.\nRates are fictional scenario parameters, not tax advice.\nDuplicates, unsupported differences, missing facts or conflicting totals must not be posted.\nAll drafts require human approval. Model suggestions must cite original documents.\n''',encoding='utf-8')
    balances={a:0 for a in ACCOUNTS};balances['1002']=10000000;balances['4001']=-10000000
    for case in answers:
        for line in case['expected_lines']:
            balances[line['account']]+=line['debit']-line['credit']
    save(output/'ground_truth/expected.json',dict(seed=seed,cases=answers,
        counts=dict(Counter(x['expected_issue_codes'][0] if x['expected_issue_codes'] else 'NORMAL' for x in answers)),
        expected_full_approved_balances=balances,
        note='Evaluation only. Never provide this directory to runtime tools. Review this synthetic oracle manually.'))
    writer=PdfWriter();catalog=[]
    for (role,variant),path in sorted(samples.items()):
        writer.append(str(path));catalog.append(dict(role=role,variant=variant,path=path.relative_to(output).as_posix()))
    with (output/'layout_preview.pdf').open('wb') as f:
        writer.write(f)
    save(output/'sample_catalog.json',catalog)
    save(output/'generation_check.json',dict(transactions=100,normal=70,review_required=30,
        documents=len(documents),bank_rows=len(bank),templates=len(samples),
        split_counts=dict(Counter(x['split'] for x in answers)),live_model_evaluation_performed=False))
    print(f'Generated {len(documents)} English PDFs, 100 transactions and {len(bank)} bank rows under {output}')

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--output',type=Path,default=ROOT/'data')
    ap.add_argument('--seed',type=int,default=566026);args=ap.parse_args()
    generate(args.output,args.seed)
