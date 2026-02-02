#!/bin/bash
# Google Cloud Run 배포 스크립트
# 실행 전 gcloud CLI 설치 및 인증 필요: gcloud auth login

set -e

# 설정
PROJECT_ID="your-gcp-project-id"
REGION="asia-northeast3"
SERVICE_NAME="goodpocket-api"

# 환경 변수 (실제 값으로 교체)
SUPABASE_URL="https://xxx.supabase.co"
SUPABASE_ANON_KEY="xxx"
SUPABASE_SERVICE_ROLE_KEY="xxx"
SUPABASE_JWT_SECRET="xxx"
DATABASE_URL="postgresql://postgres:xxx@db.xxx.supabase.co:5432/postgres"
BATCH_JOB_SECRET="your-secure-random-string"

echo "=== GoodPocket API Cloud Run 배포 ==="

# 프로젝트 설정
gcloud config set project $PROJECT_ID

# Cloud Run 배포
echo "Deploying to Cloud Run..."
gcloud run deploy $SERVICE_NAME \
  --source ./backend \
  --region $REGION \
  --platform managed \
  --allow-unauthenticated \
  --memory 1Gi \
  --cpu 1 \
  --timeout 300 \
  --min-instances 0 \
  --max-instances 2 \
  --set-env-vars "SUPABASE_URL=$SUPABASE_URL" \
  --set-env-vars "SUPABASE_ANON_KEY=$SUPABASE_ANON_KEY" \
  --set-env-vars "SUPABASE_SERVICE_ROLE_KEY=$SUPABASE_SERVICE_ROLE_KEY" \
  --set-env-vars "SUPABASE_JWT_SECRET=$SUPABASE_JWT_SECRET" \
  --set-env-vars "DATABASE_URL=$DATABASE_URL" \
  --set-env-vars "BATCH_JOB_SECRET=$BATCH_JOB_SECRET"

# 서비스 URL 가져오기
SERVICE_URL=$(gcloud run services describe $SERVICE_NAME --region $REGION --format 'value(status.url)')
echo "Service deployed at: $SERVICE_URL"

# Cloud Scheduler 설정 (배치 작업)
echo "Setting up Cloud Scheduler for batch jobs..."
gcloud scheduler jobs create http goodpocket-batch-job \
  --schedule="0 */3 * * *" \
  --uri="$SERVICE_URL/api/jobs/batch" \
  --http-method=POST \
  --headers="X-Batch-Secret=$BATCH_JOB_SECRET" \
  --location=$REGION \
  --time-zone="Asia/Seoul" \
  --attempt-deadline=540s \
  || echo "Scheduler job may already exist, updating..."

# 스케줄러 업데이트 (이미 존재하는 경우)
gcloud scheduler jobs update http goodpocket-batch-job \
  --schedule="0 */3 * * *" \
  --uri="$SERVICE_URL/api/jobs/batch" \
  --http-method=POST \
  --headers="X-Batch-Secret=$BATCH_JOB_SECRET" \
  --location=$REGION \
  --time-zone="Asia/Seoul" \
  --attempt-deadline=540s \
  || true

echo "=== 배포 완료 ==="
echo "API URL: $SERVICE_URL"
echo "Health check: $SERVICE_URL/health"
echo ""
echo "프론트엔드 .env에 설정:"
echo "VITE_API_URL=$SERVICE_URL"
