import unittest
import pandas as pd
from build_audit_metrics import DATA,extract,amount

class AuditTests(unittest.TestCase):
    def test_negative_and_unknown(self):
        self.assertEqual(amount('(37,087,058,764)'),-37087058764)
        self.assertIsNone(amount('확인 필요'))
        self.assertEqual(amount('-'),0)
    def test_gold_report_values(self):
        reports=pd.read_csv(DATA/'audit_report_index.csv',dtype=str)
        r=reports[reports.rcept_no=='20260327000901'].iloc[0]
        from build_audit_metrics import ROOT
        if not (ROOT/str(r['document_path']).replace('\\','/')).exists():
            self.skipTest('공시 원문 zip이 제출 ZIP에 없어 건너뜀 (collect_audit.py로 받은 뒤 다시 실행)')
        rows,trace,status=extract(r)
        self.assertEqual(len(rows),2)
        gold=rows[0]
        expected={'revenue':1641442498285,'op_income':-37087058764,'net_income':-44988351182,'assets':1813018064706,'liabilities':242300487437,'equity':1570717577269,'borrowings':38240605733,'interest_expense':2402539479}
        for k,v in expected.items():self.assertEqual(gold[k],v,k)
        self.assertEqual(gold['fs_div'],'OFS')
        self.assertEqual(gold['period'],'2025')
        self.assertEqual(gold['assets'],gold['liabilities']+gold['equity'])
        self.assertTrue(all(t['xml_member'] and t['source_url'] for t in trace))
    def test_fiscal_month_and_missing_stay_missing(self):
        m=pd.read_csv(DATA/'audit_metrics.csv',dtype={'stock_code':str})
        self.assertGreaterEqual(m.corp_name.nunique(),15)
        self.assertFalse(m.duplicated(['stock_code','period']).any())
        march=m[m.corp_name=='동서석유화학']
        self.assertTrue(march.period.str.endswith('FY03').all())
        self.assertTrue(march.fiscal_end.str.endswith('-03').all())
        cfs=m[(m.fs_div=='CFS')&(m.period_type=='FY')]
        self.assertTrue(cfs.roe.isna().all())
        self.assertTrue(m.stock_code.notna().all())
    def test_csv_and_quality_cover_audits(self):
        m=pd.read_csv(DATA/'metrics.csv',dtype={'stock_code':str})
        q=pd.read_csv(DATA/'data_quality.csv',dtype={'stock_code':str})
        self.assertEqual(len(m),len(q))
        audits=m[m.data_source=='AUDIT_XML']
        self.assertEqual(audits.corp_name.nunique(),16)
        self.assertTrue(audits.source_url.notna().all())
    def test_latest_reports_and_halfyear_columns(self):
        m=pd.read_csv(DATA/'metrics.csv',dtype={'stock_code':str})
        sk=m[(m.stock_code=='D00786711')&(m.period=='2025H1')].iloc[0]
        self.assertEqual(sk.revenue,2240502520000)
        self.assertEqual(sk.op_income,256550711000)
        self.assertEqual(sk.net_income,221138284000)
        self.assertEqual(sk.assets,3438790891000)
        self.assertEqual(sk.net_income_owner,216134384000)
        self.assertEqual(sk.fs_div,'CFS')
        self.assertEqual(sk.period_type,'H1')
        dl=m[(m.stock_code=='D01524817')&(m.period=='2025')].iloc[0]
        self.assertEqual(dl.assets,7394660465666)
        self.assertEqual(dl.revenue,4616114401757)
        self.assertEqual(dl.fs_div,'CFS')
        em=m[m.stock_code=='087730']
        self.assertEqual(set(em.period),{'2021','2022'})
    def test_hd_verified_borrowings(self):
        m=pd.read_csv(DATA/'metrics.csv',dtype={'stock_code':str})
        r=m[(m.stock_code=='D00105174')&(m.period=='2026H1')].iloc[0]
        self.assertEqual(r.borrowings,8467958864000)
        self.assertEqual(r.borrow_dep,round(r.borrowings/r.assets*100,2))
        q=pd.read_csv(DATA/'data_quality.csv',dtype={'stock_code':str})
        self.assertEqual(q[(q.stock_code=='D00105174')&(q.period=='2026H1')].iloc[0].management_ready,'Y')

if __name__=='__main__':unittest.main()
