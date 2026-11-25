"""Allowlisted input access, deterministic known-template parsing and indexing."""
import csv
import hashlib
import re
from decimal import Decimal
from pathlib import Path
from pypdf import PdfReader
from .core import ROOT,load,digest

FIELDS={'type':str,'number':str,'date':str,'issuer':str,'recipient':str,'reference':str,'description':str,
        'net_cents':int,'tax_cents':int,'total_cents':int,'tax_rate_bps':int,'employee':str,
        'invoice_reference':str,'completed':bool}
HEADERS={'STANDARD INVOICE':'invoice','STANDARD SERVICE AGREEMENT':'contract',
    'STANDARD DELIVERY CONFIRMATION':'acceptance','STANDARD PAYMENT RECEIPT':'receipt',
    'STANDARD EXPENSE CLAIM':'claim','STANDARD OFFICE PURCHASE ORDER':'order'}
LABELS={'Document number':'number','Document date':'date','Issued by':'issuer','Issued to':'recipient',
    'Business reference':'reference','Description':'description','Net amount CNY':'net_cents',
    'Tax amount CNY':'tax_cents','Total amount CNY':'total_cents','Demo rate bps':'tax_rate_bps',
    'Employee':'employee','Related invoice':'invoice_reference','Completion confirmed':'completed'}

def cents(text):
    value=Decimal(text.replace(',',''))*100
    if value!=value.to_integral_value():
        raise ValueError('Sub-cent value is not supported')
    return int(value)

def norm(text):
    return ' '.join(str(text).lower().split())

def known_template(text):
    first=next((line.strip() for line in text.splitlines() if line.strip() in HEADERS),'')
    if first not in HEADERS:
        return None
    result={k:None for k in FIELDS};result['type']=HEADERS[first]
    for line in text.splitlines():
        if ': ' not in line:
            continue
        label,value=line.split(': ',1)
        key=LABELS.get(label)
        if not key:
            continue
        if key.endswith('_cents'):
            result[key]=cents(value)
        elif key=='tax_rate_bps':
            result[key]=int(value)
        elif key=='completed':
            if value not in ('YES','NO'):
                raise ValueError('Unrecognized completion flag')
            result[key]=value=='YES'
        else:
            result[key]=value.strip() or None
    return result

class Store:
    def __init__(self,inp=None):
        self.inp=Path(inp or ROOT/'data/input').resolve()
        self.config=load(self.inp/'config.json')
        self.policy=(self.inp/'company_policy.txt').read_text(encoding='utf-8')
        entries=sorted(load(self.inp/'document_index.json'),key=lambda x:(x['received_at'],x['document_id']))
        self.docs={};self.records={};self.origins={};self.errors={}
        for entry in entries:
            did=entry['document_id']
            if did in self.docs:
                raise ValueError('Duplicate document ID')
            path=(self.inp/entry['path']).resolve()
            if self.inp not in path.parents or path.suffix.lower()!='.pdf':
                raise ValueError('Document path must stay inside input')
            if hashlib.sha256(path.read_bytes()).hexdigest()!=entry['sha256']:
                raise ValueError(f'Input checksum mismatch: {did}')
            try:
                pages=[p.extract_text() or '' for p in PdfReader(path).pages]
                text='\n'.join(pages)
            except Exception:
                pages=[];text='';self.errors[did]='PDF_READ_FAILED'
            if not text.strip():
                self.errors[did]='OCR_REQUIRED'
            reference=re.search(r'REF-\d+',text)
            number=re.search(r'(?:Document number|Invoice ID|Invoice reference):\s*(TEST-INV-\d+)',text)
            # Metadata identification is indexing, not semantic field extraction.
            is_invoice=bool(re.search(r'^(STANDARD INVOICE|INVOICE / BILLING ADVICE|Invoice - Account Statement|Invoice notification letter)',text,re.MULTILINE))
            self.docs[did]=dict(entry,text=text,pages=pages,reference=reference.group() if reference else None,
                invoice_number=number.group(1) if number else None,is_invoice=is_invoice)
            try:
                record=known_template(text)
                if record:
                    self.records[did]=record;self.origins[did]='python_template'
            except (ValueError,TypeError):
                self.errors[did]='TEMPLATE_PARSE_FAILED'
        self.invoices=[did for did,d in self.docs.items() if d['is_invoice']]
        with (self.inp/'bank_statement.csv').open(encoding='utf-8-sig',newline='') as f:
            rows=list(csv.DictReader(f))
        self.bank={}
        for row in rows:
            if row['bank_id'] in self.bank:
                raise ValueError('Duplicate bank ID')
            row['signed_amount_cents']=int(row['signed_amount_cents'])
            self.bank[row['bank_id']]=row
        self.seen_numbers={};self.duplicates=set()
        for did in self.invoices:
            number=self.docs[did]['invoice_number']
            if number and number in self.seen_numbers:
                self.duplicates.add(did)
            if number:
                self.seen_numbers[number]=did

    def related(self,invoice_id):
        inv=self.docs[invoice_id];terms=[x for x in (inv['reference'],inv['invoice_number']) if x]
        return [did for did,d in self.docs.items() if did!=invoice_id and not d['is_invoice']
                and any(term in d['text'] for term in terms)]

    def bank_candidates(self,invoice_id):
        ref=self.docs[invoice_id]['reference']
        return [bid for bid,b in self.bank.items() if ref and ref in b['memo']]

    def search(self,query):
        tokens=[t for t in norm(query).split() if len(t)>2]
        ranked=[]
        for did,d in self.docs.items():
            score=sum(t in norm(d['text']) for t in tokens)
            if score:
                ranked.append((score,did))
        return [dict(document_id=did,reference=self.docs[did]['reference'],
            extracted=did in self.records,excerpt=self.docs[did]['text'][:220])
            for _,did in sorted(ranked,reverse=True)[:15]]

    def fingerprint(self):
        files=['config.json','company_policy.txt','document_index.json','bank_statement.csv']
        files += [d['path'] for d in self.docs.values()]
        return digest({name:hashlib.sha256((self.inp/name).read_bytes()).hexdigest() for name in sorted(files)})
