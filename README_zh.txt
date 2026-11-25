财务记账智能体：运行与结果说明
============================

直接查看报表，无需安装、无需API：
  results/final_reviewed/financial_statements.pdf
    第1页：资产负债表。第2页：利润表。金额单位：人民币元。
  results/final_reviewed/financial_statements.html
    双击浏览器打开，两张报表均在同一页面。
  results/final_reviewed/balance_sheet.csv
  results/final_reviewed/income_statement.csv
    可用Excel查看，amount_cny为元。
  results/final_reviewed/trial_balance.csv 和 journal.csv
    试算表与分录的原始导出，金额单位为分。
  docs/project_report_zh.pdf
    正式中文报告，共9页；中文楷体，英文与数字Times New Roman。

本交付包含代码、英文输入资料、独立答案、自动测试、真实运行记录和最终账簿报表。
首次真实实验与修正后复核分开保存，不能把最终100%分录匹配当成首次独立模型成绩。
本轮100笔业务最终70笔进入模拟账簿、30笔异常保留核查。
收入55198.09元，费用106851.49元，亏损51653.40元；报表勾稽通过。

运行步骤和所有可复制命令见README.txt。主入口为main.py，不需要逐个运行accounting里的.py。
generate_data.py只生成数据；输入已经附带，通常不需要运行它。
审批完成后自动生成可读PDF、HTML及两张报表CSV。已有JSON也可重新导出：
  .\.venv\Scripts\python.exe main.py export --results results/final_reviewed
该导出不调用模型、不改动账簿。

GitHub提交清单：
必须保留 main.py、accounting/、tests/、data/input/、data/ground_truth/、requirements.txt。
建议保留 generate_data.py、docs/、README、.env.example、.gitignore、validation_report.json。
本包保留 results/full_01/、results/final_reviewed/ 和 results/recovery_audit/，用于展示和审计实验。
不要上传 .env、.venv、__pycache__、.idea、.vscode、临时运行目录。
本地继续运行时保留自己的.env和.venv；“不提交”不等于必须从电脑删除。
原项目的hybrid_01、hybrid_01_rechecked、full_01_final、完整恢复快照及诊断目录可先另行归档；
本包已用精简审计记录保存必要证据，不需要把所有中间目录都放进仓库。
data/layout_preview.pdf、sample_catalog.json、generation_check.json不被运行入口读取，本包已省略。

不要删除 accounting 中看起来“不用直接运行”的模块；main.py会按子命令导入它们。
标准答案只供evaluate和测试读取，不能加入Agent检索范围。
本包的.gitignore保留正式参考结果，但忽略后续新增的本地结果目录。
正式上传前检查git status；若Key已被跟踪，新增.gitignore不会自动从历史中移除它。
