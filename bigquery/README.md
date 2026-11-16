# BigQuery mart

프로젝트 `swift-implement-513705-i7` / 원본 `clean`(읽기만) → 결과 `mart`

| mart 테이블 | 대시보드 항목 | 정의 (최종본_ver1.ipynb 기준) | 기간 |
|---|---|---|---|
| `kpi_daily` | KPI: 방문 DAU, 완료 DAU, 방문 대비 완료 비율 | `user_day` 날짜별 고유 사용자 | 7/18~8/10 |
| `funnel_daily` | ① 완료율 추이, ② 실행→시작 퍼널, D1 재방문 | 16장 사용자×날짜 순서 퍼널 (기본 4단계 + 확장 6단계) | 7/25~8/10 (D1은 ~8/9) |
| `open_start_10m_user` | ③ 받은 투표 확인 → 10분 내 시작 (검증용) | 9장 첫 확인 기준, `in_main_analysis` = 노트북 분석 대상 | 7/18~8/10 |
| `open_start_10m_daily` | ③ 전환율 추이 | 같은 규칙을 사용자×날짜별 그날 첫 확인에 적용 | 7/18~8/10 |
| `aha_users`, `aha_by_signup_day` | KPI·④ 아하모먼트 도달률, 가입 시기별 도달률 | 17장 7/18~7/27 신규 가입자, 첫 7일 2회 이상 완료 | 가입 7/18~7/27 |
| `repeat_7d_daily` | ⑤ 이후 7일 세트 재참여율 | 18장 완료일 다음 D+1~D+7 재완료 | 7/18~8/3 |
| `weekly_return` | KPI: 다음 주 재방문율 | 이번 주 활동자 중 다음 주 활동 비율 (주평균 비율의 평균 아님) | W1·W2 |

⑥ 완료 1건당 실제 투표 수, ⑦ 0표 완료 비율은 노트북 18-1과 같이 실제 선택 이벤트·세트 ID가 없어 만들지 않았다.

## 실행

```
python bigquery/run_mart.py        # 전체 다시 만들기
python bigquery/validate_mart.py   # 노트북 숫자와 비교 (23개 항목, 하나라도 다르면 실패)
python bigquery/export_json.py     # dashboard/data.json 만들기
```

자동 갱신: `.github/workflows/update-data.yml` (매일 09:00 KST, 저장소 Secret `GCP_SA_KEY` 필요)

비율은 날짜별 분자·분모 합으로 다시 계산한다 (일별 비율의 단순 평균 아님).
