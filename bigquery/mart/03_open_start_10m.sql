-- 받은 투표 확인 → 10분 내 투표 시작률
-- 출처: clean.events_vote (숫자 ID, step 컬럼). 노트북 9장 make_anchors / ordered_chain / action_flags와 같은 규칙
--   기준 시점: 사용자의 '첫' 받은 투표 확인 (기간 내 첫 기록)
--   제외: 그날 확인 전에 이미 시작·완료함 / 확인과 같은 시각에 시작·완료 / 확인 후 30분이 그날·기간 안에 다 안 들어감
--   시작: 같은 날짜 안에서 확인보다 늦은 첫 시작이 10분 이내
-- 두 테이블을 만든다
--   open_start_10m_user : 사용자별 첫 확인 기준 (노트북 21.22% 검증용)
--   open_start_10m_daily: 사용자×날짜별 그날 첫 확인 기준, 같은 제외 규칙 (대시보드 일별 추이용)
CREATE OR REPLACE TABLE mart.open_start_10m_user AS
WITH opens AS (
  SELECT uid, MIN(event_datetime) AS open_at
  FROM clean.events_vote
  WHERE step = 'received_open' AND event_datetime >= '2023-07-18' AND event_datetime < '2023-08-11'
  GROUP BY uid
),
day_first AS (
  SELECT uid, event_date,
    MIN(IF(step = 'vote_start', event_datetime, NULL)) AS day_first_start,
    MIN(IF(step = 'set_complete', event_datetime, NULL)) AS day_first_complete
  FROM clean.events_vote WHERE step IN ('vote_start', 'set_complete')
  GROUP BY uid, event_date
),
st AS (
  SELECT uid, event_datetime AS start_at FROM clean.events_vote WHERE step = 'vote_start'
),
base AS (
  SELECT o.uid, DATE(o.open_at) AS open_day, o.open_at,
    (IFNULL(f.day_first_start < o.open_at, FALSE) OR IFNULL(f.day_first_complete < o.open_at, FALSE)) AS prior_same_day,
    (IFNULL(f.day_first_start = o.open_at, FALSE) OR IFNULL(f.day_first_complete = o.open_at, FALSE)) AS tie_at_open,
    (DATETIME_ADD(o.open_at, INTERVAL 30 MINUTE) < DATETIME(DATE_ADD(DATE(o.open_at), INTERVAL 1 DAY))
      AND DATETIME_ADD(o.open_at, INTERVAL 30 MINUTE) < '2023-08-11') AS full_window
  FROM opens o
  LEFT JOIN day_first f ON f.uid = o.uid AND f.event_date = DATE(o.open_at)
)
SELECT b.uid, b.open_day, b.open_at,
  NOT b.prior_same_day AND NOT b.tie_at_open AND b.full_window AS in_main_analysis,
  MIN(s.start_at) AS first_start_after,
  IF(MIN(s.start_at) <= DATETIME_ADD(b.open_at, INTERVAL 10 MINUTE), 1, 0) AS started_10m
FROM base b
LEFT JOIN st s ON s.uid = b.uid AND DATE(s.start_at) = b.open_day AND s.start_at > b.open_at
GROUP BY b.uid, b.open_day, b.open_at, in_main_analysis;

CREATE OR REPLACE TABLE mart.open_start_10m_daily AS
WITH opens AS (
  SELECT uid, event_date, MIN(event_datetime) AS open_at
  FROM clean.events_vote
  WHERE step = 'received_open' AND event_datetime >= '2023-07-18' AND event_datetime < '2023-08-11'
  GROUP BY uid, event_date
),
ev AS (
  SELECT uid, event_date, step, event_datetime FROM clean.events_vote WHERE step IN ('vote_start', 'set_complete')
),
per AS (
  SELECT o.uid, o.event_date, o.open_at,
    COUNTIF(e.event_datetime < o.open_at) > 0 AS prior_same_day,
    COUNTIF(e.event_datetime = o.open_at) > 0 AS tie_at_open,
    MIN(IF(e.step = 'vote_start' AND e.event_datetime > o.open_at, e.event_datetime, NULL)) AS first_start_after
  FROM opens o LEFT JOIN ev e USING (uid, event_date)
  GROUP BY o.uid, o.event_date, o.open_at
),
kept AS (
  SELECT * FROM per
  WHERE NOT prior_same_day AND NOT tie_at_open
    AND DATETIME_ADD(open_at, INTERVAL 30 MINUTE) < DATETIME(DATE_ADD(event_date, INTERVAL 1 DAY))
    AND DATETIME_ADD(open_at, INTERVAL 30 MINUTE) < '2023-08-11'
)
SELECT event_date,
  COUNT(*) AS n_open_users,
  COUNTIF(first_start_after <= DATETIME_ADD(open_at, INTERVAL 10 MINUTE)) AS n_start_10m,
  SAFE_DIVIDE(COUNTIF(first_start_after <= DATETIME_ADD(open_at, INTERVAL 10 MINUTE)), COUNT(*)) AS start_10m_rate
FROM kept
GROUP BY event_date;
