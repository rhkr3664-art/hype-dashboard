"""mart 테이블 숫자를 최종본 노트북 실행값과 비교한다 (새 지표는 기존 검증 숫자와 서로 맞는지 확인)."""
import sys
from google.cloud import bigquery
sys.stdout.reconfigure(encoding='utf-8')
c = bigquery.Client(project='swift-implement-513705-i7')
q = lambda s: list(c.query(s).result())[0]

checks = []
f = q("""SELECT SUM(n_launch) a, SUM(n_start) b, SUM(n_reaction) c, SUM(n_complete) d,
  SUM(x_open) e, SUM(x_tab) f, SUM(x_start) g, SUM(x_reaction) h, SUM(x_complete) i,
  SUM(d1_base) j, SUM(d1_return) k FROM mart.funnel_daily""")
checks += [('기본 퍼널: 앱 실행', f.a, 384111), ('기본 퍼널: 투표 시작', f.b, 90682), ('기본 퍼널: 첫 관측 반응', f.c, 69147),
           ('기본 퍼널: 세트 완료', f.d, 63360), ('확장 퍼널: 받은 투표 확인', f.e, 118279), ('확장 퍼널: 질문 탭 진입', f.f, 49487),
           ('확장 퍼널: 투표 시작', f.g, 15367), ('확장 퍼널: 첫 관측 반응', f.h, 12539), ('확장 퍼널: 세트 완료', f.i, 11609),
           ('D1 재방문: 분모', f.j, 369388), ('D1 재방문: 재방문', f.k, 104428)]
k = q("""SELECT SUM(complete_dau) a, SUM(visit_dau) b FROM mart.kpi_daily WHERE event_date >= '2023-07-25'""")
checks += [('완료 DAU 합 (7/25~)', k.a, 63585), ('방문 DAU 합 (7/25~)', k.b, 385061)]
o = q("""SELECT COUNTIF(in_main_analysis) a, SUM(IF(in_main_analysis, started_10m, 0)) b FROM mart.open_start_10m_user""")
checks += [('첫 확인 사용자', o.a, 94092), ('10분 내 시작', o.b, 19968)]
r = q("""SELECT SUM(n_complete_users) a, SUM(n_recomplete_7d) b FROM mart.repeat_7d_daily WHERE event_date >= '2023-07-25'""")
checks += [('7일 재완료: 분모 (7/25~8/3)', r.a, 37888), ('7일 재완료: 재완료', r.b, 19271)]
w = q("""SELECT n_active a, n_next_week_active b FROM mart.weekly_return WHERE week_no = 1""")
checks += [('W1 활동자 (7/18~24)', w.a, 126835), ('W2 재방문자', w.b, 33266 + 4385 + 13546)]
# 완료 후 7일 재방문·재투표 (행동 수준별): 노트북 값이 없는 새 지표라 기존 검증 숫자와 서로 맞는지로 확인
#   완료한 날(level 2·3) 합 = 7일 재완료 분모·분자, 전체 사용자·일 합 = 같은 기간 방문 DAU 합
h = q("""SELECT SUM(IF(level >= 2, n_user_days, 0)) a, SUM(IF(level >= 2, n_recomplete_7d, 0)) b, SUM(n_user_days) c,
  (SELECT SUM(visit_dau) FROM mart.kpi_daily WHERE event_date BETWEEN '2023-07-25' AND '2023-08-03') d
  FROM mart.return_7d_level_daily WHERE event_date >= '2023-07-25'""")
checks += [('7일 재방문: 완료한 날 (= 재완료 분모)', h.a, 37888), ('7일 재방문: 재투표 (= 재완료)', h.b, 19271),
           ('7일 재방문: 전체 사용자·일 (= 방문 DAU 합)', h.c, h.d)]

print(f'{"항목":<28}{"BigQuery":>10}{"노트북":>10}  결과')
for name, got, want in checks:
    print(f'{name:<28}{got:>10,}{want:>10,}  {"일치" if got == want else f"차이 {got - want:+,}"}')
bad = [n for n, g, w in checks if g != w]
if bad:
    sys.exit(f'불일치 {len(bad)}개: data.json을 만들지 않는다')
