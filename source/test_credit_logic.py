"""판정 경계와 스트레스가 실제 금융 해석을 뒤집는 경우를 검증한다."""
from pathlib import Path
import sys,unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'app'))
from credit_logic import stage,stress,headroom,loss_streak,clip_icr

class CreditTests(unittest.TestCase):
    def test_threshold_equality(self):
        self.assertEqual(stage(1,30),'관찰 (빚 부담)')
        self.assertEqual(stage(.99,30),'집중 관리')
        self.assertEqual(stage(1,29.99),'정상 관리')
        self.assertEqual(stage(.99,29.99),'관리 강화 (이익 부족)')
    def test_missing_and_invalid_equity_defer(self):
        for icr,debt,equity in [(None,20,10),(2,float('nan'),10),(2,20,0),(2,20,-10)]:
            self.assertEqual(stage(icr,debt,equity),'판정 보류')
        self.assertEqual(stage(2,20,100,ready=False),'판정 보류')
    def test_shock_can_cross_reference(self):
        self.assertAlmostEqual(stress(1.5,100,.5,.3),.75/1.3)
        self.assertEqual(stage(stress(1.5,100,.5,.3),20),'관리 강화 (이익 부족)')
    def test_losses_do_not_improve(self):
        self.assertEqual(stress(-2,-100,.5,.3),-2)
        self.assertEqual(stress(-2,-100,historical_change=-2),-2)
    def test_historical_loss_crossing(self):
        self.assertEqual(stress(4,100,historical_change=-2),-4)
    def test_headroom_reaches_one_not_below(self):
        h=headroom(5)
        self.assertAlmostEqual(stress(5,100,h/100,0),1)
        self.assertIsNone(headroom(1));self.assertIsNone(headroom(-1))
    def test_half_year_not_extra_full_year(self):
        r=[{'corp_name':'A','period':str(y),'icr':.5} for y in range(2022,2026)]
        r.append({'corp_name':'A','period':'2026H1','icr':.1})
        self.assertEqual(loss_streak(r,'A','2026H1'),4)
        self.assertEqual(loss_streak(r,'A','2023'),2)
        self.assertEqual(loss_streak([x for x in r if x['period']!='2024'],'A','2026H1'),1)
    def test_plot_clipping_preserves_actual_indicator(self):
        self.assertEqual(clip_icr(40),(15,'→'))
        self.assertEqual(clip_icr(-12),(-5,'←'))
        self.assertEqual(clip_icr(1),(1,''))
        self.assertEqual(clip_icr(None),(None,''))

if __name__=='__main__':unittest.main()
