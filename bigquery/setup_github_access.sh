#!/usr/bin/env bash
# GitHub Actions(rhkr3664-art/hype-dashboard)가 키 파일 없이 BigQuery에 접속하도록 설정한다.
# 실행: GCP 프로젝트 '소유자'가 콘솔 오른쪽 위 Cloud Shell(>_)을 열고 이 파일 내용을 붙여넣는다.
# 만드는 것
#   - 서비스 계정 hype-dashboard-actions (권한: 작업 실행, 데이터 읽기, mart 데이터셋 쓰기)
#   - Workload Identity 풀 'github' + 공급자 'github-repo' (이 저장소에서 온 요청만 허용)
# 키 파일은 만들지 않는다.
set -euo pipefail
PROJECT=swift-implement-513705-i7
REPO=rhkr3664-art/hype-dashboard
SA=hype-dashboard-actions
SA_EMAIL=$SA@$PROJECT.iam.gserviceaccount.com

gcloud config set project $PROJECT
NUM=$(gcloud projects describe $PROJECT --format='value(projectNumber)')
gcloud services enable iam.googleapis.com iamcredentials.googleapis.com sts.googleapis.com bigquery.googleapis.com

# 1) 서비스 계정과 BigQuery 권한
gcloud iam service-accounts describe $SA_EMAIL >/dev/null 2>&1 || \
  gcloud iam service-accounts create $SA --display-name="hype-dashboard GitHub Actions"
for ROLE in roles/bigquery.jobUser roles/bigquery.dataViewer; do
  gcloud projects add-iam-policy-binding $PROJECT --member="serviceAccount:$SA_EMAIL" --role=$ROLE --condition=None >/dev/null
done
bq query --nouse_legacy_sql --location=US \
  "GRANT \`roles/bigquery.dataEditor\` ON SCHEMA \`$PROJECT.mart\` TO 'serviceAccount:$SA_EMAIL'"

# 2) GitHub 저장소 연결 (Workload Identity)
gcloud iam workload-identity-pools describe github --location=global >/dev/null 2>&1 || \
  gcloud iam workload-identity-pools create github --location=global --display-name="GitHub Actions"
gcloud iam workload-identity-pools providers describe github-repo --location=global --workload-identity-pool=github >/dev/null 2>&1 || \
  gcloud iam workload-identity-pools providers create-oidc github-repo --location=global --workload-identity-pool=github \
    --issuer-uri="https://token.actions.githubusercontent.com" \
    --attribute-mapping="google.subject=assertion.sub,attribute.repository=assertion.repository" \
    --attribute-condition="assertion.repository=='$REPO'"
gcloud iam service-accounts add-iam-policy-binding $SA_EMAIL --role=roles/iam.workloadIdentityUser \
  --member="principalSet://iam.googleapis.com/projects/$NUM/locations/global/workloadIdentityPools/github/attribute.repository/$REPO" >/dev/null

echo "완료: projects/$NUM/locations/global/workloadIdentityPools/github/providers/github-repo"
echo "서비스 계정: $SA_EMAIL"
