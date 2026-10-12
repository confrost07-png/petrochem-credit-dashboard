"""metrics.csv를 SQLite에 적재하고 credit_signal_check.sql을 실행한다. (프로젝트 루트에서 실행)"""
import sqlite3
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
con = sqlite3.connect(":memory:")
df = pd.read_csv(ROOT / "data" / "processed" / "metrics.csv", encoding="utf-8-sig", dtype={"stock_code": str})
df.to_sql("metrics", con, index=False)
sql = (ROOT / "sql" / "credit_signal_check.sql").read_text(encoding="utf-8")
for i, stmt in enumerate(s for s in sql.split(";") if "SELECT" in s.upper()):
    print(f"\n[Query {i + 1}]")
    print(pd.read_sql(stmt, con).to_string(index=False))
