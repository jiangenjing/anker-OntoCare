"""Read the two original XLSX files into source JSON; requires openpyxl for this offline tool."""
import hashlib
import json
import sys
from pathlib import Path
import openpyxl

base = Path(__file__).resolve().parents[1]
folder = Path(sys.argv[1]) if len(sys.argv) > 1 else base.parent
result = []
for name in ['eufy Robovacs Q&A.xlsx', 'eufy Breast Pump Q&A.xlsx']:
    path = folder / name
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    workbook = openpyxl.load_workbook(path, read_only=True, data_only=True)
    for sheet in workbook:
        values = list(sheet.iter_rows(values_only=True))
        for number, values_row in enumerate(values[1:], 2):
            if not any(values_row):
                continue
            row = dict(zip(values[0], values_row))
            row.update(source_file=name, source_sheet=sheet.title, source_row=number, source_sha256=digest)
            result.append(row)
    workbook.close()
(base / 'data/qa-workbooks.json').write_text(json.dumps(result, ensure_ascii=False, indent=2))
print(f'Imported {len(result)} source rows. Changed sources invalidate old cache entries; review before rebuilding templates.')
