-- 완료 후 7일: 재방문(앱 활동)·재투표(세트 재완료), 그날 한 행동 수준별
--   단위: 사용자×날짜 (clean.user_day는 활동한 날만 1행)
--   level 0 = 기록 없음 (그날 투표 시작·완료 없음)
--         1 = 시작만 (시작 있음, 완료 없음)
--         2 = 완료 1회
--         3 = 완료 2회 이상
--   재방문 = D+1~D+7 중 활동한 날 있음 / 재투표 = D+1~D+7 중 세트 완료한 날 있음
--   D+7까지 전체가 보이는 날짜(~8/3)만 포함
--   level 2+3의 재투표는 04_retention.sql의 이후 7일 재완료율과 같은 값 (validate_mart.py에서 확인)
-- (기존 아하모먼트 테이블은 신규 가입자 지표라 대시보드에서 빼면서 삭제)
DROP TABLE IF EXISTS mart.aha_users;
DROP TABLE IF EXISTS mart.aha_by_signup_day;

CREATE OR REPLACE TABLE mart.return_7d_level_daily AS
WITH d AS (
  SELECT uid, event_date,
    CASE WHEN IFNULL(n_set_complete, 0) >= 2 THEN 3
         WHEN IFNULL(n_set_complete, 0) = 1 THEN 2
         WHEN IFNULL(n_vote_start, 0) > 0 THEN 1
         ELSE 0 END AS level
  FROM clean.user_day
  WHERE event_date BETWEEN '2023-07-18' AND '2023-08-03'
),
x AS (
  SELECT a.uid, a.event_date, a.level,
    LOGICAL_OR(b.uid IS NOT NULL) AS returned,
    LOGICAL_OR(IFNULL(b.n_set_complete, 0) > 0) AS recompleted
  FROM d a
  LEFT JOIN clean.user_day b
    ON b.uid = a.uid AND b.event_date > a.event_date AND b.event_date <= DATE_ADD(a.event_date, INTERVAL 7 DAY)
  GROUP BY a.uid, a.event_date, a.level
)
SELECT event_date, level,
  COUNT(*) AS n_user_days,
  COUNTIF(returned) AS n_return_7d,
  COUNTIF(recompleted) AS n_recomplete_7d
FROM x
GROUP BY event_date, level;
