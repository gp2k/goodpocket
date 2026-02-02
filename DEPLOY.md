# 배포 가이드 (Cloudflare Pages + Railway)

## 아키텍처

- **Frontend**: Cloudflare Pages (Vite/React)
- **Backend**: Railway (FastAPI)
- **Database / Auth**: Supabase (기존)

---

## 0단계: GitHub 저장소 생성 및 푸시

Railway와 Cloudflare Pages는 GitHub 저장소와 연동해 배포합니다. 아직 저장소가 없다면 먼저 생성하세요.

1. [GitHub](https://github.com/new)에서 **New repository** 클릭
2. Repository name: `goodpocket` (또는 원하는 이름)
3. **Create repository** 후 안내되는 명령어로 로컬 코드 푸시:

```powershell
cd c:\Users\gp2k\source\repos\goodpocket
git init
git add .
git commit -m "Initial commit"
git branch -M main
git remote add origin https://github.com/<your-username>/goodpocket.git
git push -u origin main
```

이미 다른 이름으로 저장소를 만들었다면, 아래 단계에서 해당 저장소를 선택하면 됩니다.

---

## 1단계: Backend를 Railway에 배포

### 1.1 Railway 프로젝트 생성

**중요:** 모노레포이므로 반드시 Backend 서비스의 **Root Directory**를 `backend`로 설정해야 합니다. 설정하지 않으면 "Error creating build plan with Railpack" 오류가 납니다.

**방법 A – 저장소 연결 후 설정**

1. [Railway](https://railway.app) 로그인 후 **New Project** 클릭
2. **Deploy from GitHub repo** 선택 후 위에서 푸시한 저장소 연결
3. Backend 서비스 클릭 → **Settings** 탭
4. **Root Directory**에 `backend` 입력 후 **Deploy** (또는 변경 사항 저장 후 재배포)
5. **Deploy** 실행

**방법 B – 빈 프로젝트에서 먼저 설정 (권장)**

1. **New Project** → **Empty project** 선택
2. **+ New** → **Empty Service** 로 서비스 추가 후 이름을 "Backend" 등으로 변경
3. 해당 서비스 **Settings** → **Root Directory**를 `backend`로 설정
4. **Source**에서 **Connect Repo**로 GitHub 저장소 연결
5. **Deploy** 실행

### 1.2 환경변수 설정 (Railway Dashboard)

Project > Variables에서 다음 변수 추가:

| 변수명 | 설명 |
|--------|------|
| `SUPABASE_URL` | Supabase 프로젝트 URL |
| `SUPABASE_ANON_KEY` | Supabase anon key |
| `SUPABASE_SERVICE_ROLE_KEY` | Supabase service role key |
| `SUPABASE_JWT_SECRET` | Supabase JWT secret |
| `DATABASE_URL` | Supabase Connection string (Direct connection) |
| `BATCH_JOB_SECRET` | 배치 작업용 시크릿 (예: goodpocket-secret-batch-5814) |

### 1.3 도메인 확인

Railway가 생성한 Public URL을 복사 (예: `https://goodpocket-production.up.railway.app`).  
이 URL을 Frontend 환경변수 `VITE_API_URL`에 사용합니다.

---

## 2단계: Frontend를 Cloudflare Pages에 배포

### 2.1 Cloudflare Pages 프로젝트 생성

1. [Cloudflare Dashboard](https://dash.cloudflare.com) > **Workers & Pages** > **Create** > **Pages** > **Connect to Git**
2. GitHub에서 위 0단계로 푸시한 저장소 선택
3. 빌드 설정:
   - **Framework preset**: Vite
   - **Build command**: `npm run build`
   - **Build output directory**: `dist`
   - **Root directory**: `frontend`

### 2.2 환경변수 설정 (Cloudflare Pages)

Settings > Environment variables (Production)에서 추가:

| 변수명 | 값 |
|--------|-----|
| `VITE_SUPABASE_URL` | `https://dzcxxilkzqjulokoxind.supabase.co` |
| `VITE_SUPABASE_ANON_KEY` | Supabase anon key |
| `VITE_API_URL` | Railway Backend URL (1단계에서 복사한 URL) |

### 2.3 .env.production 업데이트

Railway URL을 확인한 뒤 `frontend/.env.production`의 `VITE_API_URL`을 실제 Railway URL로 수정하고, Cloudflare에서 동일한 값으로 환경변수를 설정합니다.

---

## 3단계: Supabase 설정 업데이트

1. Supabase Dashboard > **Authentication** > **URL Configuration**
2. **Site URL**: `https://goodpocket.pages.dev` (또는 사용 중인 Cloudflare Pages 도메인)
3. **Redirect URLs**에 추가:
   - `https://goodpocket.pages.dev/`
   - `https://goodpocket.pages.dev/**`
   - 커스텀 도메인을 쓰면 해당 도메인도 추가

---

## 배포 후 체크리스트

- [ ] Railway: Backend Health check (`https://<railway-url>/health`) 응답 확인
- [ ] Cloudflare Pages: 빌드 성공 및 사이트 접속 확인
- [ ] 로그인: OAuth(Google/GitHub) 및 이메일 로그인 테스트
- [ ] API: 북마크 저장/목록 API 호출 테스트
- [ ] CORS: 브라우저 콘솔에 CORS 에러 없는지 확인

---

## 문제 해결

### "Error creating build plan with Railpack" (Railway)

- **원인:** 저장소 루트에서 빌드되어 `backend/` 안의 Python이 인식되지 않음.
- **해결:** Backend 서비스 **Settings** → **Root Directory**를 `backend`로 설정한 뒤 다시 배포.
- 프로젝트를 지우고, **Empty project** → **Empty Service** 생성 → Root Directory `backend` 설정 → **Connect Repo** 순서로 다시 시도해도 됩니다.

### CORS 에러

Backend `backend/app/main.py`의 `allow_origins`에 사용 중인 Frontend 도메인을 추가합니다.

### Railway "Build timed out" / "importing to docker" 후 실패

- **원인:** (1) 빌드 단계가 오래 걸리거나 (2) **이미지가 너무 커서** 푸시/임포트 단계에서 타임아웃됨 (torch + CUDA 조합 시 이미지가 수 GB).
- **해결:** Dockerfile에서 **CPU 전용 PyTorch**를 먼저 설치하도록 되어 있음 (`torch --index-url https://download.pytorch.org/whl/cpu`). Railway는 GPU가 없으므로 CPU 버전으로 충분하며, 이미지 크기가 줄어 푸시가 완료되기 쉬움. 그래도 실패하면 Railway **Project** → **Settings**에서 빌드 타임아웃을 늘리거나, 로그 끝 단계를 확인하세요.

### Railway PORT

Railway는 `PORT` 환경변수를 제공합니다. `Procfile`·`nixpacks.toml`에서 `$PORT`를 사용하므로 별도 설정 없이 동작합니다.

### Cloudflare 빌드 실패

- Root directory가 `frontend`인지 확인
- Node 버전: Cloudflare 기본 버전 사용. 필요 시 Build command에 `npx vite build` 등 명시
