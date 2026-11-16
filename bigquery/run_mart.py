"""mart 데이터셋을 만들고 SQL 파일을 순서대로 실행한다.
사용: python run_mart.py            (전체)
      python run_mart.py 02         (파일 이름에 02가 들어간 것만)
원본(clean) 테이블은 읽기만 한다."""
import sys, pathlib, time
from google.cloud import bigquery
sys.stdout.reconfigure(encoding='utf-8')
P = 'swift-implement-513705-i7'
c = bigquery.Client(project=P)
loc = c.get_dataset(f'{P}.clean').location
ds = bigquery.Dataset(f'{P}.mart'); ds.location = loc
c.create_dataset(ds, exists_ok=True)
print(f'mart 데이터셋 준비 완료 (위치 {loc})')
pick = sys.argv[1] if len(sys.argv) > 1 else ''
for f in sorted((pathlib.Path(__file__).parent / 'mart').glob('*.sql')):
    if pick not in f.name:
        continue
    sql = f.read_text(encoding='utf-8')
    t = time.time()
    job = c.query(sql, location=loc)
    job.result()
    billed = sum((ch.total_bytes_billed or 0) for ch in c.list_jobs(parent_job=job.job_id)) or (job.total_bytes_billed or 0)
    print(f'{f.name}: 완료 {time.time() - t:.0f}초, 처리 {billed / 1e9:.2f}GB')
