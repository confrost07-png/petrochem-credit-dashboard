"""외부 API 대신 격리된 응답으로 수집 중단·부분 성공·별도 기준을 검증한다."""
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase,main
from unittest.mock import patch,Mock
import sys,json,importlib.util
import pandas as pd
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'source'),str(ROOT/'app')]
import collect_expanded as collector
import data_update
from collection_status import missing_message
spec=importlib.util.spec_from_file_location('clean_test',ROOT/'source/02_clean.py')
cleaner=importlib.util.module_from_spec(spec);spec.loader.exec_module(cleaner)

class CollectionTests(TestCase):
    def setUp(self):
        (ROOT/'.deck_work').mkdir(exist_ok=True)  # 새 폴더·맥·코랩에서도 임시 폴더가 있도록
        self.temp=TemporaryDirectory(dir=ROOT/'.deck_work')
        self.path=Path(self.temp.name).resolve()
        assert self.path.is_relative_to((ROOT/'.deck_work').resolve())
        self.raw=self.path/'raw';self.raw.mkdir()
        self.data=self.path/'processed';self.data.mkdir()
        self.patches=[patch.object(collector,'RAW',self.raw),patch.object(collector,'DATA',self.data),
                      patch.object(collector,'read_key',return_value='test-key'),patch.object(collector.time,'sleep')]
        for p in self.patches:p.start()
    def tearDown(self):
        for p in reversed(self.patches):p.stop()
        self.temp.cleanup()
    def test_ofs_fallback_and_metadata(self):
        no=Mock();no.json.return_value={'status':'013'}
        yes=Mock();yes.json.return_value={'status':'000','list':[{'rcept_no':'123','account_nm':'자산총계'}]}
        corp={'stock_code':'051910','corp_code':'00356361'}
        with patch.object(collector.requests,'get',side_effect=[no,yes]) as get:
            result=collector.fetch(corp,2025,'11011','test-key')
        self.assertEqual(result['fs_div'],'OFS')
        self.assertEqual(get.call_args_list[1].kwargs['params']['fs_div'],'OFS')
        cached=json.loads((self.raw/'051910_2025_11011.json').read_text(encoding='utf-8'))
        self.assertEqual(cached['_collection']['fs_div'],'OFS')
        self.assertNotIn('test-key',str(cached))
        self.assertEqual(collector.fetch(corp,2025,'11011','')['fs_div'],'OFS')
    def test_partial_success_is_counted_and_deferred(self):
        corp={'corp_name':'테스트','stock_code':'051910','corp_code':'00356361','corp_cls':'Y'}
        good={'status':'000','fs_div':'CFS','rows':1,'rcept_no':'123','note':'연결'}
        bad={'status':'NETWORK_ERROR','fs_div':'CFS','rows':0,'rcept_no':'','note':'연결 실패'}
        with patch.object(collector,'registry',return_value=[corp]),patch.object(collector,'fetch',side_effect=[good,bad,bad,bad]):
            result=collector.collect(company='051910')
        self.assertTrue(result['network_halted'])
        self.assertEqual(result['new_reports'],1)
        coverage=pd.read_csv(self.data/'collection_coverage.csv',dtype=str)
        self.assertEqual(coverage.iloc[0]['period'],'2026H1')
        self.assertIn('DEFERRED_NETWORK',coverage.status.tolist())
        self.assertNotIn('013',coverage.status.tolist())
    def test_partial_success_rebuilds_even_when_connection_halts(self):
        result={'network_halted':True,'new_reports':1,'selected_reports':1}
        with patch.object(collector,'collect',return_value=result),patch.object(data_update.runpy,'run_path') as rebuild:
            self.assertEqual(data_update.update_company('051910'),result)
            rebuild.assert_called_once()
    def test_network_diagnosis_does_not_claim_invalid_key(self):
        with patch.object(collector.requests,'get',side_effect=collector.requests.ConnectionError('private-url')):
            result=collector.diagnose()
        self.assertEqual(result['api_status'],'NETWORK_ERROR')
        self.assertNotIn('private-url',str(result))
        self.assertNotIn('test-key',str(result))
    def test_network_and_unprovided_have_different_messages(self):
        def message(code):
            cov=pd.DataFrame([{'corp_name':'LG화학','period':'2026H1','status':code}])
            return missing_message('LG화학','2026H1',cov)
        self.assertIn('연결 실패',message('NETWORK_ERROR'))
        self.assertIn('미제공',message('013'))
        self.assertNotIn('미제공',message('NETWORK_ERROR'))
    def test_combined_borrowings_do_not_double_count_components(self):
        def row(code,name,amount):return {'sj_div':'BS','account_id':code,'account_nm':name,
            'thstrm_amount':str(amount),'frmtrm_amount':str(amount),'rcept_no':'123','ord':'1'}
        rows=[row('ifrs-full_CurrentBorrowingsAndCurrentPortionOfNoncurrentBorrowings','유동차입금',1000),
              row('ifrs-full_CurrentPortionOfLongtermBorrowings','유동성장기차입금',200),
              row('dart_CurrentPortionOfBonds','유동성사채',300),
              row('ifrs-full_LongtermBorrowings','사채 및 장기차입금',2000),
              row('dart_BondsIssued','사채',500)]
        (self.raw/'051910_2025_11011.json').write_text(json.dumps({'status':'000','list':rows}),encoding='utf-8')
        with patch.object(cleaner,'RAW_DIR',self.raw),patch.object(cleaner,'TARGETS',{'051910':'테스트'}),patch.object(cleaner,'ANNUAL_YEARS',[2025]):
            data,mapping,_=cleaner.clean()
        fy=data[data.period=='2025']
        self.assertEqual(fy.value_krw.sum(),3000)
        included=mapping[mapping.match_method.str.startswith('included_in_')]
        self.assertEqual(len(included),3)
        self.assertTrue(included.account_id.ne('').all())
    def test_cleaner_preserves_ofs_basis_without_row_field(self):
        payload={'status':'000','_collection':{'fs_div':'OFS'},'list':[{'sj_div':'BS','account_id':'ifrs-full_Equity'}]}
        (self.raw/'051910_2025_11011.json').write_text(json.dumps(payload),encoding='utf-8')
        with patch.object(cleaner,'RAW_DIR',self.raw):
            rows,_=cleaner.load_rows('051910',2025,'11011')
        self.assertEqual(rows[0]['fs_div'],'OFS')
    def test_current_split_requires_exact_liability_reconciliation(self):
        def row(code,name,amount):return {'sj_div':'BS','account_id':code,'account_nm':name,
            'thstrm_amount':str(amount),'frmtrm_amount':str(amount),'rcept_no':'123','ord':'1'}
        rows=[row('ifrs-full_ShorttermBorrowings','단기차입금',1000),
              row('ifrs-full_CurrentBorrowingsAndCurrentPortionOfNoncurrentBorrowings','유동성 대체 부분',2000),
              row('ifrs-full_OtherCurrentLiabilities','기타유동부채',500),
              row('ifrs-full_CurrentLiabilities','유동부채',3500)]
        p=self.raw/'051910_2025_11011.json'
        for total,expected in [(3500,3000),(3502,1000)]:
            rows[-1]['thstrm_amount']=str(total)
            p.write_text(json.dumps({'status':'000','list':rows}),encoding='utf-8')
            with patch.object(cleaner,'RAW_DIR',self.raw),patch.object(cleaner,'TARGETS',{'051910':'테스트'}),patch.object(cleaner,'ANNUAL_YEARS',[2025]):
                data,_,_=cleaner.clean()
            self.assertEqual(data[data.period=='2025'].value_krw.sum(),expected)

if __name__=='__main__':main()
