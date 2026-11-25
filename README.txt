FINANCIAL ACCOUNTING AGENT
==========================

Python-first bookkeeping with optional DeepSeek extraction and tool-based investigation.
The package contains source code, synthetic input documents, tests, formal documentation,
the initial real API experiment, reviewed ledger entries and readable financial statements.

OPEN RESULTS WITHOUT INSTALLING OR CALLING AN API

  results/final_reviewed/financial_statements.pdf
    Page 1: BALANCE SHEET. Page 2: INCOME STATEMENT. Values are in CNY (yuan).
  results/final_reviewed/financial_statements.html
    Double-click to view both statements in a browser. No web server or login is required.
  results/final_reviewed/balance_sheet.csv
  results/final_reviewed/income_statement.csv
    Open in Excel; amount_cny is yuan, not cents.
  results/final_reviewed/trial_balance.csv
  results/final_reviewed/journal.csv
    Original machine exports; amounts are integer CNY cents, divide by 100 for yuan.
  docs/project_report_zh.pdf
    Formal Chinese system design, processing steps and experiment report (9 pages).

REFERENCE OUTCOME

100 synthetic transactions: 70 reviewed normal entries in the simulated ledger; 30 anomalies held.
Revenue CNY 55,198.09; expenses CNY 106,851.49; loss CNY 51,653.40.
Assets CNY 51,658.47; liabilities CNY 3,311.87; equity CNY 48,346.60.
All report controls and independent synthetic balance checks passed.
Initial real run: 90% clean-journal accuracy, 30/30 anomalies held, 7 normal cases escalated.
Final reviewed scores include code corrections and targeted re-extraction; they are development
results, not an untouched independent test. Exact issue-set accuracy is 97%, not 100%.
743 real model requests in the recorded experiment: 707 initial, 35 recovery, 1 diagnostic.
This release does not make any API call merely by opening reports or running export.

PROJECT CONTENTS

  main.py                   CLI: doctor, run, summary, evaluate, approve, recheck, export.
  accounting/               Processing, audit, client, approval, evaluation and presentation modules.
  tests/                    Control/integration tests with scripted model doubles; no live calls.
  generate_data.py          Optional dataset generator; data is already bundled.
  data/input/               264 English text-layer PDFs, 101 bank rows, index, config and policy.
  data/ground_truth/        Isolated benchmark answers; never provide these to model tools.
  results/full_01/          Initial real cases, evaluation, request usage and trace.
  results/final_reviewed/   Reviewed final cases, decisions, ledger, reports and readable statements.
  results/recovery_audit/   Compact recovery traces, usage and initial source hashes.
  docs/                    Formal project report.
  .env.example              Empty key configuration sample.
  .gitignore                Excludes secrets/caches/new runs, preserves curated reference results.
  validation_report.json   Validation record, including real-vs-scripted evaluation distinctions.

SETUP (Windows PowerShell, Python 3.10+)

  py -m venv .venv
  .\.venv\Scripts\python.exe -m pip install -r requirements.txt
  .\.venv\Scripts\python.exe main.py doctor

OFFLINE RUN (no model calls)

  .\.venv\Scripts\python.exe main.py run --mode offline --limit 6 --out results/offline_01
  .\.venv\Scripts\python.exe main.py summary --results results/offline_01
  .\.venv\Scripts\python.exe main.py evaluate --results results/offline_01

Unsupported layouts are held in offline mode. It does not pretend to understand unknown documents.

LIVE API RUN (optional; use your own local key)

  Copy-Item .env.example .env
Fill DEEPSEEK_API_KEY locally in .env. The default model is configurable via DEEPSEEK_MODEL.
  .\.venv\Scripts\python.exe main.py doctor --check-api
  .\.venv\Scripts\python.exe main.py run --mode hybrid --limit 6 --max-calls 100 --out results/hybrid_new
  .\.venv\Scripts\python.exe main.py evaluate --results results/hybrid_new

For 100 new cases use --limit 100 and a sufficient --max-calls budget (for example 1200).
Request limits are not monetary caps. Read actual provider billing for charges.
Use a fresh output folder; do not overwrite the delivered reference results.

APPROVAL AND FINANCIAL EXPORTS

Review cases.json against sources. Copy review_template.json to a decision file, change only checked
decisions from reject to approve, and preserve snapshot_hash.
  .\.venv\Scripts\python.exe main.py approve --results results/hybrid_new --decisions decisions.json
Approval recomputes controls and creates financial_statements.pdf/html and both statement CSVs.
No AI can approve or post. Model tools never access ground_truth.
cases.json remains a frozen draft snapshot; actual approved count is in reports.json/ledger.json.
To re-export readable statements from existing approved reports without an API call:
  .\.venv\Scripts\python.exe main.py export --results results/final_reviewed

Recheck is optional after control changes; it reuses frozen records, not a new model experiment:
  .\.venv\Scripts\python.exe main.py recheck --results results/hybrid_new --out results/rechecked_new

TESTS

  .\.venv\Scripts\python.exe -m unittest -v

GITHUB CONTENTS

Commit this clean package, including curated reference results, docs, tests and data.
Do NOT commit .env, .venv, __pycache__, .idea, .vscode or newly generated local runs.
The supplied .gitignore deliberately keeps full_01, final_reviewed and recovery_audit.
Review `git status` before publishing. A key accidentally committed must be revoked and removed
from repository history; .gitignore alone does not untrack existing files.
GITHUB_CONTENTS.txt lists keep/exclude choices.

SCOPE

English text PDFs, one fictional business, October 2026 and CNY. No scanning/OCR, tax filing,
arbitrary third-party layouts or external ERP posting. Demo tax assumptions and simplified
statements are educational. No measured 50% human-time saving or independent generalisation
claim has been established. Actual source documents were not edited to satisfy controls.
