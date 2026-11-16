-- 일별 핵심 KPI: 방문 DAU, 완료 DAU, 방문 대비 완료 비율
-- 출처: clean.user_day (숫자 ID). 노트북 18장 nbx_visit_dau / nbx_complete_dau와 같은 정의
-- 기간: hackle 전체 7/18~8/10 (대시보드에서 7/25~ 필터 가능)
CREATE OR REPLACE TABLE mart.kpi_daily AS
SELECT
  event_date,
  COUNT(DISTINCT uid) AS visit_dau,
  COUNT(DISTINCT IF(n_set_complete > 0, uid, NULL)) AS complete_dau,
  SAFE_DIVIDE(COUNT(DISTINCT IF(n_set_complete > 0, uid, NULL)), COUNT(DISTINCT uid)) AS complete_user_rate,
  COUNT(DISTINCT IF(n_vote_start > 0, uid, NULL)) AS start_dau,
  COUNT(DISTINCT IF(n_received_open > 0, uid, NULL)) AS received_open_dau
FROM clean.user_day
WHERE event_date BETWEEN '2023-07-18' AND '2023-08-10'
GROUP BY event_date;
