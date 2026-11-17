"""mart 테이블을 읽어 대시보드용 data.json을 만든다.
사용: python bigquery/export_json.py            → docs/data.json (GitHub Pages가 docs 폴더를 공개)
      python bigquery/export_json.py 경로.json
KPI 카드 기간은 노트북과 같은 7/25~8/10 (A/B 테스트 전 기준 기간). 비율은 분자·분모 합으로 계산한다."""
import sys, json, pathlib, datetime as dt
from google.cloud import bigquery
sys.stdout.reconfigure(encoding='utf-8')
P = 'swift-implement-513705-i7'
ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT = pathlib.Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / 'docs' / 'data.json'
KPI_START, KPI_END = '2023-07-25', '2023-08-10'
c = bigquery.Client(project=P)


def rows(sql):
    out = []
    for r in c.query(sql).result():
        d = dict(r.items())
        for k, v in d.items():
            if isinstance(v, (dt.date, dt.datetime)): d[k] = v.isoformat()
            elif isinstance(v, float): d[k] = round(v, 6)
        out.append(d)
    return out


def one(sql): return rows(sql)[0]


def rate(num, den, label, unit='%'):
    return {'label': label, 'value': round(num / den * 100, 2) if den else None, 'numerator': num, 'denominator': den, 'unit': unit}


f = one(f"""SELECT SUM(n_launch) launch, SUM(n_start) start, SUM(n_reaction) reaction, SUM(n_complete) complete,
  SUM(x_open) x_open, SUM(x_tab) x_tab, SUM(x_start) x_start, SUM(x_reaction) x_reaction, SUM(x_complete) x_complete,
  SUM(d1_base) d1_base, SUM(d1_return) d1_return FROM mart.funnel_daily""")
k = one(f"""SELECT SUM(visit_dau) visit, SUM(complete_dau) complete, COUNT(*) days FROM mart.kpi_daily
  WHERE event_date BETWEEN '{KPI_START}' AND '{KPI_END}'""")
o = one("SELECT COUNTIF(in_main_analysis) n, SUM(IF(in_main_analysis, started_10m, 0)) s FROM mart.open_start_10m_user")
r = one(f"SELECT SUM(n_complete_users) n, SUM(n_recomplete_7d) s FROM mart.repeat_7d_daily WHERE event_date >= '{KPI_START}'")
a = one("SELECT COUNT(*) n, SUM(aha_reached) s, SUM(IF(aha_reached=1,w2_return,0)) r1, SUM(IF(aha_reached=0,w2_return,0)) r0 FROM mart.aha_users")
w = rows("SELECT week_no, week_start, n_active, n_next_week_active, next_week_return_rate FROM mart.weekly_return ORDER BY week_no")

data = {
    'meta': {
        'title': '익명 투표 앱 서비스 현황 대시보드',
        'generated_at': dt.datetime.now(dt.timezone(dt.timedelta(hours=9))).isoformat(timespec='seconds'),
        'source': f'BigQuery {P}.mart',
        'kpi_period': [KPI_START, KPI_END],
        'note': 'KPI 기간은 A/B 테스트 전 기준 기간. 퍼널·D1은 사용자×날짜 단위, 아하모먼트는 7/18~7/27 신규 가입자 기준',
    },
    'kpi': {
        'visit_dau_avg': {'label': '방문 DAU (일평균)', 'value': round(k['visit'] / k['days'], 1), 'unit': '명'},
        'complete_dau_avg': {'label': '완료 DAU (일평균)', 'value': round(k['complete'] / k['days'], 1), 'unit': '명'},
        'launch_to_complete': rate(f['complete'], f['launch'], '앱 실행 → 세트 완료율'),
        'launch_to_start': rate(f['start'], f['launch'], '앱 실행 → 투표 시작률'),
        'start_to_complete': rate(f['complete'], f['start'], '투표 시작 → 세트 완료율'),
        'open_start_10m': rate(o['s'], o['n'], '받은 투표 확인 → 10분 내 시작률'),
        'aha_rate': rate(a['s'], a['n'], '첫 7일 2회 완료 도달률 (아하모먼트)'),
        'recomplete_7d': rate(r['s'], r['n'], '이후 7일 세트 재완료율'),
        'd1_return': rate(f['d1_return'], f['d1_base'], '앱 실행일 기준 D1 재방문율'),
        'next_week_return': rate(w[0]['n_next_week_active'], w[0]['n_active'], '다음 주 재방문율 (7/18주 → 7/25주)'),
    },
    'funnel': {
        'basic': [{'step': s, 'n': n} for s, n in [('앱 실행', f['launch']), ('투표 시작', f['start']),
                                                  ('첫 관측 반응', f['reaction']), ('세트 완료', f['complete'])]],
        'extended': [{'step': s, 'n': n} for s, n in [('앱 실행', f['launch']), ('받은 투표 확인', f['x_open']),
                                                     ('질문 탭 진입', f['x_tab']), ('투표 시작', f['x_start']),
                                                     ('첫 관측 반응', f['x_reaction']), ('세트 완료', f['x_complete'])]],
    },
    'daily': rows("""
        SELECT k.event_date AS date, k.visit_dau, k.complete_dau, k.complete_user_rate,
          f.n_launch, f.n_start, f.n_reaction, f.n_complete,
          f.x_open, f.x_tab, f.x_start, f.x_reaction, f.x_complete,
          SAFE_DIVIDE(f.n_start, f.n_launch) AS launch_to_start, SAFE_DIVIDE(f.n_complete, f.n_launch) AS launch_to_complete,
          f.d1_base, f.d1_return, SAFE_DIVIDE(f.d1_return, f.d1_base) AS d1_return_rate,
          o.n_open_users, o.n_start_10m, o.start_10m_rate,
          r.n_complete_users, r.n_recomplete_7d, r.recomplete_7d_rate
        FROM mart.kpi_daily k
        LEFT JOIN mart.funnel_daily f USING (event_date)
        LEFT JOIN mart.open_start_10m_daily o USING (event_date)
        LEFT JOIN mart.repeat_7d_daily r USING (event_date)
        ORDER BY date"""),
    'aha': {
        'reached_w2_return': round(a['r1'] / a['s'] * 100, 2),
        'not_reached_w2_return': round(a['r0'] / (a['n'] - a['s']) * 100, 2),
        'by_signup_day': rows("SELECT * FROM mart.aha_by_signup_day ORDER BY signup_day"),
    },
    'weekly_return': w,
    'not_available': ['완료 1건당 실제 투표 수', '0표 완료 비율'],
}
OUT.parent.mkdir(parents=True, exist_ok=True)
OUT.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
print(f'저장: {OUT} ({OUT.stat().st_size / 1024:.1f}KB, 일별 {len(data["daily"])}행)')
for v in data['kpi'].values():
    print(f"  {v['label']}: {v['value']}{v['unit']}")
