-- 일별 기본·확장 퍼널 (사용자×날짜) + 앱 실행일 기준 D1 재방문
-- 출처: clean.additional_events(실행·세션 시작·질문 탭) + clean.events_vote_funnel(확인·시작·스킵·완료)
--       + clean.user_day_funnel(D1 재방문). 모두 u_ ID 패키지. 노트북 16장·18장과 같은 정의
-- 기간: 7/25~8/10 (질문 탭 기록이 7/25부터 안정)
-- 규칙
--   앱 실행: launch_app 또는 $session_start, 사용자×날짜별 가장 이른 시각
--   다음 단계: 같은 날짜 안에서 앞 단계보다 '늦은' 첫 기록 (같은 시각 불인정)
--   시도: 시작 이벤트 한 건 = 한 시도. 반응·완료는 그 시작 이후~다음 시작 전까지만 연결
--   같은 초에 시작이 여러 건이면 그 시도의 반응·완료 연결 보류
--   하루 여러 시도 중 가장 깊이 진행한 시도로 도달 단계 판정
CREATE OR REPLACE TABLE mart.funnel_daily AS
WITH ev AS (
  SELECT uid, event_key, event_datetime AS t, DATE(event_datetime) AS d
  FROM clean.additional_events
  WHERE event_key IN ('launch_app', '$session_start', 'view_questions_tap')
  UNION ALL
  SELECT uid, event_key, event_datetime, DATE(event_datetime)
  FROM clean.events_vote_funnel
  WHERE event_key IN ('click_question_open', 'click_question_start', 'skip_question', 'complete_question')
),
ev_p AS (
  SELECT * FROM ev WHERE t >= '2023-07-25' AND t < '2023-08-11'
),
launch AS (
  SELECT uid, d, MIN(t) AS launch_at
  FROM ev_p WHERE event_key IN ('launch_app', '$session_start')
  GROUP BY uid, d
),
-- 시도 (같은 시각 시작은 한 행으로 묶고 개수를 센다)
starts AS (
  SELECT uid, d, t AS start_at, COUNT(*) AS n_same
  FROM ev_p WHERE event_key = 'click_question_start'
  GROUP BY uid, d, t
),
attempts0 AS (
  SELECT *, LEAD(start_at) OVER (PARTITION BY uid, d ORDER BY start_at) AS next_start_at
  FROM starts
),
attempts AS (
  SELECT a.uid, a.d, a.start_at,
    -- 시작 직후 첫 반응/완료. 다음 시작 이후거나 동시각 시작이면 연결 안 함
    IF(a.n_same = 1 AND (a.next_start_at IS NULL OR r.first_react < a.next_start_at), r.first_react, NULL) AS reaction_at,
    IF(a.n_same = 1 AND (a.next_start_at IS NULL OR r.first_done < a.next_start_at), r.first_done, NULL) AS complete_at
  FROM attempts0 a
  LEFT JOIN (
    SELECT a2.uid, a2.d, a2.start_at,
      MIN(IF(e.event_key IN ('skip_question', 'complete_question'), e.t, NULL)) AS first_react,
      MIN(IF(e.event_key = 'complete_question', e.t, NULL)) AS first_done
    FROM attempts0 a2
    JOIN ev_p e ON e.uid = a2.uid AND e.d = a2.d AND e.t > a2.start_at
     AND e.event_key IN ('skip_question', 'complete_question')
    GROUP BY a2.uid, a2.d, a2.start_at
  ) r USING (uid, d, start_at)
),
-- 기본 퍼널: 실행 이후 시도 중 가장 깊은 것
basic AS (
  SELECT l.uid, l.d,
    MAX(IF(a.start_at IS NOT NULL, 1, 0)) AS s_start,
    MAX(IF(a.reaction_at IS NOT NULL, 1, 0)) AS s_react,
    MAX(IF(a.complete_at IS NOT NULL, 1, 0)) AS s_done
  FROM launch l
  LEFT JOIN attempts a ON a.uid = l.uid AND a.d = l.d AND a.start_at > l.launch_at
  GROUP BY l.uid, l.d
),
-- 확장 퍼널: 실행 → 받은 투표 확인 → 질문 탭 → 시작 → 반응 → 완료
open_step AS (
  SELECT l.uid, l.d, l.launch_at, MIN(e.t) AS open_at
  FROM launch l JOIN ev_p e
    ON e.uid = l.uid AND e.d = l.d AND e.event_key = 'click_question_open' AND e.t > l.launch_at
  GROUP BY l.uid, l.d, l.launch_at
),
tab_step AS (
  SELECT o.uid, o.d, MIN(e.t) AS tab_at
  FROM open_step o JOIN ev_p e
    ON e.uid = o.uid AND e.d = o.d AND e.event_key = 'view_questions_tap' AND e.t > o.open_at
  GROUP BY o.uid, o.d
),
ext AS (
  SELECT tb.uid, tb.d,
    MAX(IF(a.start_at IS NOT NULL, 1, 0)) AS x_start,
    MAX(IF(a.reaction_at IS NOT NULL, 1, 0)) AS x_react,
    MAX(IF(a.complete_at IS NOT NULL, 1, 0)) AS x_done
  FROM tab_step tb
  LEFT JOIN attempts a ON a.uid = tb.uid AND a.d = tb.d AND a.start_at > tb.tab_at
  GROUP BY tb.uid, tb.d
),
-- D1 재방문: 다음 날 user_day_funnel에 활동 기록이 있으면 인정. 마지막 날(8/10)은 제외
d1 AS (
  SELECT l.uid, l.d, IF(n.uid IS NOT NULL, 1, 0) AS returned
  FROM launch l
  LEFT JOIN clean.user_day_funnel n ON n.uid = l.uid AND n.event_date = DATE_ADD(l.d, INTERVAL 1 DAY)
  WHERE l.d <= '2023-08-09'
)
SELECT
  l.d AS event_date,
  COUNT(*) AS n_launch,
  SUM(b.s_start) AS n_start,
  SUM(b.s_react) AS n_reaction,
  SUM(b.s_done) AS n_complete,
  COUNT(o.uid) AS x_open,
  COUNT(tb.uid) AS x_tab,
  SUM(IFNULL(x.x_start, 0)) AS x_start,
  SUM(IFNULL(x.x_react, 0)) AS x_reaction,
  SUM(IFNULL(x.x_done, 0)) AS x_complete,
  COUNTIF(d1.uid IS NOT NULL) AS d1_base,
  SUM(IFNULL(d1.returned, 0)) AS d1_return
FROM launch l
JOIN basic b USING (uid, d)
LEFT JOIN open_step o USING (uid, d)
LEFT JOIN tab_step tb USING (uid, d)
LEFT JOIN ext x USING (uid, d)
LEFT JOIN d1 USING (uid, d)
GROUP BY event_date;
