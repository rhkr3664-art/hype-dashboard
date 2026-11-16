-- 아하모먼트: 가입 첫 7일 세트 2회 이상 완료 (노트북 17장과 같은 정의)
--   대상: 7/18~7/27 가입자 중 가입 후 14일이 모두 보이는 사람. 첫 주에 활동하지 않은 사람도 분모 포함
--   첫 7일 = 가입일(0일째)~6일째, 다음 주 = 7~13일째
-- aha_users       : 신규 가입자 1명 = 1행
-- aha_by_signup_day: 가입 날짜별 도달률 (대시보드 '가입 시기별 도달률')
CREATE OR REPLACE TABLE mart.aha_users AS
WITH nu AS (
  SELECT user_id AS uid, signup_at, DATE(signup_at) AS signup_day
  FROM clean.user_base
  WHERE signup_at >= '2023-07-18' AND signup_at < '2023-07-28'
    AND DATE_ADD(DATE(signup_at), INTERVAL 14 DAY) <= '2023-08-11'
),
j AS (
  SELECT nu.uid, DATE_DIFF(d.event_date, nu.signup_day, DAY) AS age_day, d.n_set_complete, d.n_vote_start
  FROM nu JOIN clean.user_day d ON d.uid = nu.uid
)
SELECT nu.uid, nu.signup_at, nu.signup_day,
  IFNULL(SUM(IF(j.age_day BETWEEN 0 AND 6, j.n_set_complete, 0)), 0) AS sets_w1,
  IF(IFNULL(SUM(IF(j.age_day BETWEEN 0 AND 6, j.n_set_complete, 0)), 0) >= 2, 1, 0) AS aha_reached,
  IF(COUNTIF(j.age_day BETWEEN 7 AND 13) > 0, 1, 0) AS w2_return,
  IF(COUNTIF(j.age_day BETWEEN 7 AND 13 AND j.n_vote_start > 0) > 0, 1, 0) AS w2_start
FROM nu LEFT JOIN j USING (uid)
GROUP BY nu.uid, nu.signup_at, nu.signup_day;

CREATE OR REPLACE TABLE mart.aha_by_signup_day AS
SELECT signup_day,
  COUNT(*) AS n_new_users,
  SUM(aha_reached) AS n_aha,
  SAFE_DIVIDE(SUM(aha_reached), COUNT(*)) AS aha_rate,
  SAFE_DIVIDE(SUM(IF(aha_reached = 1, w2_return, 0)), SUM(aha_reached)) AS w2_return_reached,
  SAFE_DIVIDE(SUM(IF(aha_reached = 0, w2_return, 0)), COUNTIF(aha_reached = 0)) AS w2_return_not_reached
FROM mart.aha_users
GROUP BY signup_day;
