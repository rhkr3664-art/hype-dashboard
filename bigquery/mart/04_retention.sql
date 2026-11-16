-- 반복 참여·재방문
-- repeat_7d_daily : 세트를 완료한 사용자×날짜 중 D+1~D+7에 다시 완료한 비율 (노트북 18장 '이후 7일 세트 재완료율')
--                   D+7까지 전체가 보이는 날짜(~8/3)만 포함
-- weekly_return   : 이번 주 활동자 중 다음 주에도 한 번 이상 활동한 비율 (노트북 4-6-3과 같은 정의)
--                   주 = 7/18~24, 7/25~31, 8/1~7 (8/8~10은 다음 주가 없어 제외)
CREATE OR REPLACE TABLE mart.repeat_7d_daily AS
WITH done AS (
  SELECT DISTINCT uid, event_date FROM clean.user_day
  WHERE n_set_complete > 0 AND event_date BETWEEN '2023-07-18' AND '2023-08-10'
)
SELECT a.event_date,
  COUNT(DISTINCT a.uid) AS n_complete_users,
  COUNT(DISTINCT IF(b.uid IS NOT NULL, a.uid, NULL)) AS n_recomplete_7d,
  SAFE_DIVIDE(COUNT(DISTINCT IF(b.uid IS NOT NULL, a.uid, NULL)), COUNT(DISTINCT a.uid)) AS recomplete_7d_rate
FROM done a
LEFT JOIN done b
  ON b.uid = a.uid AND b.event_date > a.event_date AND b.event_date <= DATE_ADD(a.event_date, INTERVAL 7 DAY)
WHERE a.event_date <= '2023-08-03'
GROUP BY a.event_date;

CREATE OR REPLACE TABLE mart.weekly_return AS
WITH wk AS (
  SELECT DISTINCT uid, DIV(DATE_DIFF(event_date, DATE '2023-07-18', DAY), 7) + 1 AS week_no
  FROM clean.user_day
  WHERE event_date BETWEEN '2023-07-18' AND '2023-08-07'
)
SELECT a.week_no,
  DATE_ADD(DATE '2023-07-18', INTERVAL (a.week_no - 1) * 7 DAY) AS week_start,
  COUNT(*) AS n_active,
  COUNTIF(b.uid IS NOT NULL) AS n_next_week_active,
  SAFE_DIVIDE(COUNTIF(b.uid IS NOT NULL), COUNT(*)) AS next_week_return_rate
FROM wk a
LEFT JOIN wk b ON b.uid = a.uid AND b.week_no = a.week_no + 1
WHERE a.week_no <= 2
GROUP BY a.week_no;
