-- data/processed/metrics.csv 를 metrics 테이블로 적재한 뒤 실행 (sql/run_sql.py)
-- 분석 대상 3사: 롯데케미칼(011170) · 대한유화(006650) · 금호석유화학(011780)

-- 1) 2021~2025 영업적자 연도 수와 이자보상배율 1배 미만 연도 수
SELECT corp_name,
       SUM(op_income < 0)  AS 영업적자_연도,
       SUM(icr < 1)        AS 이자보상배율_1배미만_연도,
       ROUND(MIN(debt_ratio), 2) AS 최저_부채비율,
       ROUND(MAX(debt_ratio), 2) AS 최고_부채비율
FROM metrics
WHERE stock_code IN ('011170', '006650', '011780')
  AND period_type = 'FY'
GROUP BY corp_name
ORDER BY 영업적자_연도 DESC;

-- 2) 부채비율은 낮은데 이자보상배율이 1배 미만인 연도 (부채비율만 보면 놓치는 위험)
SELECT corp_name, period, ROUND(debt_ratio, 2) AS 부채비율, ROUND(icr, 2) AS 이자보상배율
FROM metrics
WHERE stock_code IN ('011170', '006650', '011780')
  AND debt_ratio < 50 AND icr < 1
ORDER BY corp_name, period;

-- 3) 2026 상반기: 흑자 전환했지만 기준선(이자보상배율 1배, 차입금 의존도 30%)을 못 넘는 곳
SELECT corp_name, ROUND(op_margin, 2) AS 영업이익률, ROUND(icr, 2) AS 이자보상배율,
       ROUND(borrow_dep, 2) AS 차입금의존도,
       CASE WHEN icr < 1 AND borrow_dep >= 30 THEN '집중 관리'
            WHEN icr < 1 OR borrow_dep >= 30 THEN '주의'
            ELSE '정상' END AS 참고_판정
FROM metrics
WHERE stock_code IN ('011170', '006650', '011780') AND period = '2026H1';
