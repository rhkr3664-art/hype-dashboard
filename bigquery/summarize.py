"""docs/data.json의 전주 대비 변화를 LLM(Google Gemini API 무료 등급)이 3줄로 요약해 data.json의 'summary'에 저장한다.
사용: python bigquery/summarize.py              → GitHub Actions에서 실행 (Secret GEMINI_API_KEY 필요)
      python bigquery/summarize.py --mock       → API 호출 없이 가짜 응답으로 검증 로직만 시험
키는 Google AI Studio(aistudio.google.com)에서 발급. 결제(billing)를 연결하지 않아야 무료 등급으로 유지된다.
(GitHub Models는 2026-07-30 종료되어 Gemini로 교체)

전주 대비 = 최신 데이터일까지 직전 7일 vs 그 전 7일 (대시보드 KPI 배지와 같은 계산).
안전장치: 요약에 나온 숫자가 우리가 넘긴 숫자 목록에 하나라도 없으면 저장하지 않는다 (AI가 숫자를 지어내는 것 방지).
요약이 실패해도 대시보드 갱신은 멈추지 않는다 (summary 없이 저장 → 대시보드에서 요약 박스만 숨김)."""
import sys, os, re, json, pathlib, datetime as dt, urllib.request, urllib.error
sys.stdout.reconfigure(encoding='utf-8')
ROOT = pathlib.Path(__file__).resolve().parent.parent
PATH = ROOT / 'docs' / 'data.json'
MODEL = os.environ.get('GEMINI_MODEL', 'gemini-flash-latest')   # 최신 Flash 별칭 (없으면 사용 가능한 Flash 모델 자동 선택)
API = 'https://generativelanguage.googleapis.com/v1beta'
RATE_PP, COUNT_PCT, REL_PCT = 1.0, 5, 50   # 대시보드와 같은 증감 기준

# 대시보드 METRICS와 같은 정의 (num/den 합으로 비율, avg는 일평균)
METRICS = [
    ('앱 실행 → 세트 완료율 (핵심)', 'rate', 'n_complete', 'n_launch', 1),
    ('앱 실행 → 투표 시작률', 'rate', 'n_start', 'n_launch', 1),
    ('받은 투표 확인 → 10분 내 시작률', 'rate', 'n_start_10m', 'n_open_users', 1),
    ('방문 DAU (일평균)', 'avg', 'visit_dau', None, 0),
    ('가드레일 · 받은 투표 공유 이용률', 'rate', 'n_open_share_days', 'n_open_days', 1),
    ('가드레일 · 질문 신고 사용자 비율', 'rel', 'n_report_days', 'n_active_days', 3),
    ('가드레일 · 차단 사용자 비율', 'rel', 'n_block_days', 'n_active_days', 3),
]
WD = '월화수목금토일'


def mdw(iso):
    d = dt.date.fromisoformat(iso)
    return f'{d.month}/{d.day}({WD[d.weekday()]})'


def facts(D):
    rows = {r['date']: r for r in D['daily']}
    last = dt.date.fromisoformat(D['daily'][-1]['date'])
    span = lambda s, e: [rows[k] for k in ((last - dt.timedelta(days=i)).isoformat() for i in range(s, e + 1)) if k in rows]
    A, B = span(0, 6), span(7, 13)
    pa = f'{mdw((last - dt.timedelta(days=6)).isoformat())}~{mdw(last.isoformat())}'
    pb = f'{mdw((last - dt.timedelta(days=13)).isoformat())}~{mdw((last - dt.timedelta(days=7)).isoformat())}'
    out = []
    for label, kind, num, den, dg in METRICS:
        def val(rs):
            if kind == 'avg':
                xs = [r[num] for r in rs if r.get(num) is not None]
                return sum(xs) / len(xs) if xs else None
            rs = [r for r in rs if r.get(num) is not None and r.get(den)]
            d = sum(r[den] for r in rs)
            return sum(r[num] for r in rs) / d if d else None
        a, b = val(A), val(B)
        if a is None or b is None:
            continue
        if kind == 'avg':
            fa, fb = f'{round(a):,}명', f'{round(b):,}명'
            r = (a - b) / b * 100
            ch, big = f'{r:+.1f}%', abs(r) >= COUNT_PCT
        elif kind == 'rel':
            fa, fb = f'{a * 100:.{dg}f}%', f'{b * 100:.{dg}f}%'
            r = (a - b) / b * 100 if b else 0
            ch, big = f'{r:+.0f}% (상대 변화)', abs(r) >= REL_PCT
        else:
            fa, fb = f'{a * 100:.{dg}f}%', f'{b * 100:.{dg}f}%'
            pp = (a - b) * 100
            ch, big = f'{pp:+.1f}%p', abs(pp) >= RATE_PP
            r = pp
        verdict = ('크게 오름' if r > 0 else '크게 내림') if big else '기준 안 변화 (거의 그대로)'
        out.append({'지표': label, '직전 7일': fa, '그 전 7일': fb, '변화': ch, '판정': verdict})
    return {'직전 7일': pa, '그 전 7일': pb, '지표': out}


NUM = re.compile(r'\d[\d,]*(?:\.\d+)?')


def allowed_numbers(F):
    text = json.dumps(F, ensure_ascii=False)
    nums = {n.replace(',', '') for n in NUM.findall(text)}
    return nums | {'7', '3'}   # '직전 7일', '3줄' 같은 표현 허용


def check(lines, F):
    if len(lines) != 3:
        return f'줄 수가 3이 아님 ({len(lines)}줄)'
    ok = allowed_numbers(F)
    bad = [n for l in lines for n in NUM.findall(l) if n.replace(',', '') not in ok]
    return f'데이터에 없는 숫자: {bad}' if bad else None


PROMPT = """너는 익명 투표 앱 서비스 현황 대시보드의 요약을 쓰는 데이터 분석가야.
아래 JSON은 '직전 7일 vs 그 전 7일' 지표 비교야. PM 팀장이 바로 읽을 수 있게 한국어 3줄로 요약해.

규칙
- 정확히 3줄. 줄 앞에 번호·기호를 붙이지 마.
- 1줄: 핵심 지표(앱 실행 → 세트 완료율) 변화. 2줄: 나머지 참여 지표 중 눈에 띄는 것. 3줄: 가드레일(공유·신고·차단)이 괜찮은지.
- 숫자는 JSON에 있는 값을 그대로 옮겨 써. 계산하거나 반올림하거나 새 숫자를 만들지 마.
- '판정'이 '기준 안 변화'면 '거의 그대로'라고 쓰고 과장하지 마. 원인은 추측하지 마.
- 한 줄은 60자 안팎, 쉬운 말로.

데이터
"""


def _call(method, url, key, payload=None, timeout=240):
    req = urllib.request.Request(url, method=method, headers={'x-goog-api-key': key, 'Content-Type': 'application/json'},
                                 data=json.dumps(payload).encode() if payload is not None else None)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        raise RuntimeError(f'HTTP {e.code}: {e.read().decode(errors="replace")[:300]}') from None


def pick_model(key):
    """MODEL 별칭이 없을 때: 키로 쓸 수 있는 모델 목록에서 고른다.
    1순위 hydrogen(AI Studio 기본 무료 모델, 2026-11 기준) → 2순위 Flash 계열 최신."""
    names = [m['name'].split('/')[-1] for m in _call('GET', f'{API}/models?pageSize=200', key).get('models', [])
             if 'generateContent' in m.get('supportedGenerationMethods', [])]
    ok = lambda n: not any(x in n for x in ('lite', 'image', 'tts', 'audio', 'embed', 'preview'))
    for word in ('hydrogen', 'flash'):
        cand = sorted(n for n in names if word in n and ok(n))
        if cand:
            return cand[-1]
    raise RuntimeError(f'쓸 수 있는 모델을 못 찾음: {names[:15]}')


def ask_llm(F):
    key = os.environ.get('GEMINI_API_KEY')
    if not key:
        raise RuntimeError('GEMINI_API_KEY 없음 (GitHub Secret 등록 필요)')
    # 생각(thinking) 단계를 낮게 해서 응답을 빠르게 (지원 안 하는 모델이면 빼고 다시 요청)
    cfg = {'temperature': 0.2, 'thinkingConfig': {'thinkingLevel': 'low'}}
    payload = lambda: {'contents': [{'role': 'user', 'parts': [{'text': PROMPT + json.dumps(F, ensure_ascii=False, indent=1)}]}],
                       'generationConfig': cfg}
    model, last = MODEL, None
    for attempt in range(4):
        t0 = dt.datetime.now()
        try:
            res = _call('POST', f'{API}/models/{model}:generateContent', key, payload())
            print(f'Gemini 응답: {model}, {(dt.datetime.now() - t0).seconds}초')
            break
        except Exception as e:
            last, msg = e, str(e)
            print(f'시도 {attempt + 1} 실패 ({model}, {(dt.datetime.now() - t0).seconds}초): {msg[:200]}')
            if 'API_KEY' in msg:
                raise
            if 'thinking' in msg.lower() and 'thinkingConfig' in cfg:
                cfg.pop('thinkingConfig')
            elif 'HTTP 404' in msg or ('HTTP 400' in msg and model == MODEL):
                model = pick_model(key); print(f'→ {model} 모델로 다시 시도')
            elif 'timed out' not in msg and 'HTTP 5' not in msg and 'HTTP 429' not in msg:
                raise
    else:
        raise RuntimeError(f'4번 시도 모두 실패: {last}')
    try:
        return ''.join(p.get('text', '') for p in res['candidates'][0]['content']['parts'] if not p.get('thought')), model
    except (KeyError, IndexError):
        raise RuntimeError(f'응답에 요약이 없음: {json.dumps(res, ensure_ascii=False)[:300]}')


def to_lines(text):
    lines = [re.sub(r'^\s*(?:[-*•·]|\d+[.)])\s*', '', l).strip() for l in text.strip().splitlines()]
    return [l for l in lines if l]


def main():
    D = json.loads(PATH.read_text(encoding='utf-8'))
    D.pop('summary', None)
    F = facts(D)
    mock = '--mock' in sys.argv
    try:
        if mock:
            m = F['지표']
            text = '\n'.join([f"1. 핵심 세트 완료율은 {m[0]['직전 7일']}로 그 전 7일({m[0]['그 전 7일']})과 비교해 {m[0]['변화']}예요.",
                              f"- 투표 시작률은 {m[1]['직전 7일']}, 10분 내 시작률은 {m[2]['직전 7일']}예요.",
                              '공유·신고·차단은 기준 안이라 사용자 경험은 괜찮아요.'])
        else:
            text, used = ask_llm(F)
        lines = to_lines(text)
        err = check(lines, F)
        if err:
            raise ValueError(f'검증 실패 → 저장 안 함: {err}\n응답: {text}')
        D['summary'] = {
            'lines': lines, 'model': 'mock' if mock else used,
            'period_a': F['직전 7일'], 'period_b': F['그 전 7일'],
            'generated_at': dt.datetime.now(dt.timezone(dt.timedelta(hours=9))).isoformat(timespec='seconds'),
            'verified': True,
        }
        print('요약 저장:'); [print('  ' + l) for l in lines]
    except (Exception) as e:
        print(f'::warning::AI 요약 건너뜀 — {e}')
    PATH.write_text(json.dumps(D, ensure_ascii=False, indent=2), encoding='utf-8')


if __name__ == '__main__':
    main()
