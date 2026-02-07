# GoodPocket - Bookmark Clustering

URL 북마크를 저장하고 자동으로 태그/클러스터링하는 웹 애플리케이션입니다.

## 주요 기능

- URL 저장 시 자동 콘텐츠 추출 및 태그 생성
- 머신러닝 기반 북마크 클러스터링 (HDBSCAN + UMAP)
- 한국어/영어 콘텐츠 지원
- Supabase Auth 기반 사용자 인증

## 기술 스택

### Backend
- Python 3.11, FastAPI, Uvicorn
- asyncpg + pgvector
- trafilatura (콘텐츠 추출)
- YAKE (키워드 추출)
- sentence-transformers (임베딩)
- HDBSCAN + UMAP (클러스터링)

### Frontend
- Vite + React + TypeScript
- Tailwind CSS
- Supabase Auth

### Infrastructure
- Database: Supabase (PostgreSQL + pgvector)
- Backend: Google Cloud Run
- Frontend: Cloudflare Pages

## 로컬 개발 환경 설정

### 사전 요구사항
- Python 3.11+
- Node.js 18+
- Supabase 프로젝트 (무료 티어 가능)

### Backend 설정

```powershell
# 1. backend 폴더로 이동
cd backend

# 2. Python 가상환경 생성
python -m venv .venv

# 3. 가상환경 활성화 (Windows PowerShell)
.\.venv\Scripts\Activate.ps1

# 4. 의존성 설치
pip install -r requirements.txt

# 5. 환경 변수 설정
copy .env.example .env
# .env 파일을 열어 Supabase 정보 입력

# 6. 개발 서버 실행
uvicorn app.main:app --reload --port 8000
```

### Frontend 설정

```powershell
# 1. frontend 폴더로 이동
cd frontend

# 2. 의존성 설치
npm install

# 3. 환경 변수 설정
copy .env.example .env
# .env 파일을 열어 Supabase 정보 입력

# 4. 개발 서버 실행
npm run dev
```

### Supabase 설정

1. [Supabase](https://supabase.com)에서 새 프로젝트 생성
2. SQL Editor에서 마이그레이션을 **순서대로** 실행: `001_initial_schema.sql` → `002_add_bookmark_fields.sql` → (선택) `003_dup_groups_topics_embeddings.sql`
3. Settings > Database에서 Connection string 복사
4. Settings > API에서 URL, anon key, service role key 복사
5. Settings > Auth에서 JWT Secret 복사

기존 북마크를 새 클러스터링(dup_groups/topics) 방식으로 마이그레이션하려면 003 적용 후 `backend/scripts/migrate_to_dup_topics.py`를 실행하세요. 자세한 내용은 [DEPLOY.md](DEPLOY.md)의 "DB 마이그레이션 및 기존 북마크 → 새 클러스터링 마이그레이션" 절을 참고하세요.

## 테스트 실행

```powershell
cd backend
.\.venv\Scripts\Activate.ps1
pytest -v
```

## 배포

### Supabase 데이터베이스

1. Dashboard > Database > Extensions에서 `vector` 활성화
2. SQL Editor에서 마이그레이션 실행
3. Auth > Settings에서 이메일 인증 활성화

### Cloud Run (Backend)

```bash
# Google Cloud SDK 설치 필요
gcloud run deploy goodpocket-api \
  --source ./backend \
  --region asia-northeast3 \
  --allow-unauthenticated \
  --set-env-vars "SUPABASE_URL=https://xxx.supabase.co" \
  --set-env-vars "SUPABASE_ANON_KEY=xxx" \
  --set-env-vars "SUPABASE_SERVICE_ROLE_KEY=xxx" \
  --set-env-vars "SUPABASE_JWT_SECRET=xxx" \
  --set-env-vars "DATABASE_URL=postgresql://..." \
  --set-env-vars "BATCH_JOB_SECRET=xxx"
```

### Cloud Scheduler (배치 작업)

```bash
gcloud scheduler jobs create http goodpocket-batch \
  --schedule="0 */3 * * *" \
  --uri="https://your-cloudrun-url/api/jobs/batch" \
  --http-method=POST \
  --headers="X-Batch-Secret=your-batch-secret"
```

### Cloudflare Pages (Frontend)

```bash
cd frontend
npm run build
npx wrangler pages deploy dist --project-name goodpocket
```

Cloudflare Pages에서 환경 변수 설정:
- `VITE_SUPABASE_URL`
- `VITE_SUPABASE_ANON_KEY`
- `VITE_API_URL` (Cloud Run URL)

## API 엔드포인트

| Method | Path | Description |
|--------|------|-------------|
| POST | /api/bookmarks | 새 북마크 저장 |
| GET | /api/bookmarks | 북마크 목록 조회 |
| GET | /api/bookmarks/{id} | 북마크 상세 |
| DELETE | /api/bookmarks/{id} | 북마크 삭제 |
| GET | /api/clusters | 클러스터 목록 |
| GET | /api/clusters/{id} | 클러스터 상세 |
| POST | /api/jobs/batch | 배치 작업 트리거 |

## 환경 변수

### Backend (.env)
```
SUPABASE_URL=https://xxx.supabase.co
SUPABASE_ANON_KEY=xxx
SUPABASE_SERVICE_ROLE_KEY=xxx
SUPABASE_JWT_SECRET=xxx
DATABASE_URL=postgresql://...
BATCH_JOB_SECRET=xxx
```

### Frontend (.env)
```
VITE_SUPABASE_URL=https://xxx.supabase.co
VITE_SUPABASE_ANON_KEY=xxx
VITE_API_URL=http://localhost:8000
```

## 라이선스

MIT
