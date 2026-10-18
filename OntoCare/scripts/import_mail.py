"""Read the supplied workbook into the merchant demo; never change the workbook."""
import argparse
import json
from pathlib import Path
import openpyxl

parser = argparse.ArgumentParser()
parser.add_argument('workbook', type=Path)
args = parser.parse_args()
workbook = openpyxl.load_workbook(args.workbook, read_only=True, data_only=True)
sheet = workbook['客诉工单信息']
rows = list(sheet.values)
required = {'产品名', '客户首封邮件内容', '订单号', 'SKU', '咨询场景'}
if not required.issubset(rows[0]):
    raise ValueError('Missing required mail columns')
data = [dict(zip(rows[0], row), source_row=n) for n, row in enumerate(rows[1:], 2) if any(row)]
output = Path(__file__).resolve().parents[1] / 'data/mail-tickets.json'
output.write_text(json.dumps({'source_file':args.workbook.name, 'sheet':sheet.title, 'rows':data}, ensure_ascii=False, indent=2, default=str))
print(f'Imported {len(data)} emails to {output.name}')
