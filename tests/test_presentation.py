import csv,tempfile,unittest
from pathlib import Path
from pypdf import PdfReader
from accounting.core import ROOT,load,reports
from accounting.presentation import export_statements,statement_rows

class PresentationTests(unittest.TestCase):
    def test_saved_statements_export_exact_currency_and_two_pages(self):
        truth=load(ROOT/'data/ground_truth/expected.json')
        config=load(ROOT/'data/input/config.json')
        ledger=[dict(invoice_id=c['invoice_id'],lines=c['expected_lines']) for c in truth['cases'] if c['expected_lines']]
        report=reports(config,ledger)
        with tempfile.TemporaryDirectory() as d:
            out=Path(d);files=export_statements(out,report,'Synthetic Test Company')
            self.assertTrue(all(p.exists() for p in files))
            self.assertEqual(len(PdfReader(out/'financial_statements.pdf').pages),2)
            with (out/'balance_sheet.csv').open(encoding='utf-8-sig',newline='') as f:
                rows=list(csv.DictReader(f))
            self.assertEqual(next(r['amount_cny'] for r in rows if r['line_item']=='Total assets'),'51658.47')
            self.assertIn('51,653.40',(out/'financial_statements.html').read_text())

    def test_unreconciled_report_cannot_be_exported(self):
        config=load(ROOT/'data/input/config.json');report=reports(config,[])
        report['balance_sheet']['assets_cents']+=1
        with self.assertRaises(ValueError):
            statement_rows(report)

if __name__=='__main__':
    unittest.main()
