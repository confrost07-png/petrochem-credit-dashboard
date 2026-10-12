from pathlib import Path
import csv
ROOT=Path(__file__).resolve().parents[1]

def registry(include_candidates=True):
    p=ROOT/'data/processed/company_registry.csv'
    if not p.exists():
        return [{'stock_code':s,'corp_name':n,'corp_code':c} for s,n,c in
                [('011170','롯데케미칼','00165413'),('006650','대한유화','00260383'),('011780','금호석유화학','00106368')]]
    with p.open(encoding='utf-8-sig') as f:rows=list(csv.DictReader(f))
    cp=ROOT/'data/processed/company_candidates.csv'
    if include_candidates and cp.exists():
        with cp.open(encoding='utf-8-sig') as f:rows.extend(csv.DictReader(f))
    return rows

def target_names():return {r['stock_code']:r['corp_name'] for r in registry()}
