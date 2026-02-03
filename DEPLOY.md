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

## 4단계: Cloudflare Pages용 Google OAuth 설정

프로덕션(Cloudflare Pages)에서 "Google로 계속하기"가 동작하려면 **Google Cloud Console**에서 OAuth 클라이언트를 만들고, **Supabase**에 등록해야 합니다.

### 4.1 Google Cloud Console에서 OAuth 클라이언트 만들기

1. [Google Cloud Console](https://console.cloud.google.com/) 접속 후 로그인
2. 상단 프로젝트 선택 → **새 프로젝트** 생성(또는 기존 프로젝트 선택)
3. **APIs & Services** > **OAuth consent screen**
   - User Type: **External** 선택 후 **Create**
   - App name: `GoodPocket` (또는 원하는 이름)
   - User support email, Developer contact email 입력 후 **Save and Continue**
   - Scopes: **Add or remove scopes** → `.../auth/userinfo.email`, `.../auth/userinfo.profile` 추가 후 **Save and Continue**
   - Test users: 로그인 허용할 Gmail 주소 추가(앱이 "Testing" 상태일 때) 후 **Save and Continue**
4. **APIs & Services** > **Credentials** > **+ Create Credentials** > **OAuth client ID**
   - Application type: **Web application**
   - Name: `GoodPocket Web` (또는 원하는 이름)
   - **Authorized redirect URIs**에서 **+ ADD URI** 클릭 후 아래 주소 **그대로** 입력:
     ```
     https://dzcxxilkzqjulokoxind.supabase.co/auth/v1/callback
     ```
     (Supabase 프로젝트가 다르면 Dashboard > Project Settings > API에서 URL 확인 후 `https://<프로젝트-ref>.supabase.co/auth/v1/callback` 로 넣기)
   - **Create** 클릭
5. 생성된 **Client ID**와 **Client secret**을 복사해 둡니다(나중에 Supabase에 붙여넣기).

### 4.2 Supabase에 Google Provider 설정

1. **Supabase Dashboard** > **Authentication** > **Providers**
2. **Google** 행에서 **Enable** 토글 켜기
3. **Client ID (for OAuth)**: Google에서 복사한 Client ID 붙여넣기
4. **Client Secret (for OAuth)**: Google에서 복사한 Client secret 붙여넣기
5. **Save** 클릭

### 4.3 확인 사항

- **3단계**에서 **Site URL**과 **Redirect URLs**에 Cloudflare Pages 주소(`https://goodpocket.pages.dev` 등)가 들어가 있어야 로그인 후 다시 사이트로 돌아옵니다.
- 로컬에서 테스트할 때는 **Redirect URLs**에 `http://localhost:5173/`, `http://localhost:5173/**` 도 추가해 두면 됩니다.
- Google OAuth consent screen이 **Testing** 상태면, **Test users**에 추가한 Gmail만 로그인 가능합니다. 모두에게 열려 있게 하려면 **Publish app**으로 승인 요청을 제출해야 합니다.

### (참고) GitHub OAuth

GitHub으로 로그인도 쓰는 경우:

1. [GitHub Developer Settings](https://github.com/settings/developers) > **OAuth Apps** > **New OAuth App**
2. **Authorization callback URL**: `https://dzcxxilkzqjulokoxind.supabase.co/auth/v1/callback` (Supabase 프로젝트에 맞게 수정)
3. **Generate a new client secret** 후 Client ID / Secret 복사
4. Supabase Dashboard > **Authentication** > **Providers** > **GitHub** 에서 Enable 후 ID/Secret 입력 후 Save

---

## 배포 후 체크리스트

- [ ] Railway: Backend Health check (`https://<railway-url>/health`) 응답 확인
- [ ] Cloudflare Pages: 빌드 성공 및 사이트 접속 확인
- [ ] 로그인: OAuth(Google/GitHub) 및 이메일 로그인 테스트
- [ ] API: 북마크 저장/목록 API 호출 테스트
- [ ] CORS: 브라우저 콘솔에 CORS 에러 없는지 확인

---

## 로컬에서는 되는데 클라우드에서 안 될 때

로컬에서는 로그인·북마크가 잘 되는데, Cloudflare Pages / Railway 배포 환경에서만 안 된다면 아래를 순서대로 확인하세요.

### 1. 프론트엔드 환경 변수 (Cloudflare Pages)

빌드 시점에 `VITE_*` 값이 들어가야 합니다. **Settings > Environment variables**에서 **Production**에 다음이 있는지 확인하세요.

| 변수 | 확인 |
|------|------|
| `VITE_SUPABASE_URL` | Supabase 프로젝트 URL (예: `https://xxx.supabase.co`) |
| `VITE_SUPABASE_ANON_KEY` | Supabase anon key |
| `VITE_API_URL` | **Railway 백엔드 URL** (예: `https://xxx.up.railway.app`). **반드시 https로 끝나야 하며, 끝에 `/` 없이** |

`VITE_API_URL`이 비어 있거나 `http://localhost:8000`이면 프로덕션에서 API 요청이 실패합니다. 값 수정 후 **다시 빌드(재배포)** 해야 반영됩니다.

### 2. Supabase URL 설정

**Supabase Dashboard > Authentication > URL Configuration**에서:

- **Site URL**: 프로덕션 주소 (예: `https://goodpocket.pages.dev`)
- **Redirect URLs**에 다음이 포함되어 있는지:
  - `https://goodpocket.pages.dev/`
  - `https://goodpocket.pages.dev/**`
  - 배포별 URL을 쓴다면 `https://xxxxx.goodpocket.pages.dev/` 도 추가

이게 잘못되면 로그인 후 리다이렉트가 실패하거나 세션이 유지되지 않을 수 있습니다.

### 3. Railway 백엔드가 떠 있는지

- Railway 서비스가 **크래시 루프**에 빠져 있으면 API 호출이 502/연결 실패로 끝납니다.
- Dashboard에서 **Deployments** 상태가 성공(녹색)인지, **Logs**에 `Application startup complete` 같은 메시지가 나오는지 확인하세요.
- Supabase 프로젝트가 **Paused** 상태면 백엔드가 DB에 연결하지 못해 기동에 실패할 수 있습니다. Supabase에서 **Restore project** 후 다시 확인하세요.

### 4. CORS

- 백엔드 `main.py`에서 `https://goodpocket.pages.dev`와 `*.goodpocket.pages.dev`(배포별 URL)가 허용되어 있습니다.
- 브라우저 **개발자 도구 > Console**에 CORS 관련 에러가 있는지 확인하세요. 다른 도메인을 쓰면 **문제 해결 > CORS 에러**처럼 백엔드 `allow_origins` / `allow_origin_regex`에 해당 도메인을 추가해야 합니다.

### 5. 브라우저에서 직접 확인

- **F12 > Network**: 로그인 버튼 클릭 시 `/auth/v1/...`(Supabase), `/api/...`(Railway) 요청이 나가는지, 상태 코드가 200/302인지 확인.
- **Console**: `Failed to fetch`, `CORS`, `401`, `502` 등 에러 메시지가 있으면 그 내용을 기준으로 위 1~4를 다시 점검하면 됩니다.

---

## 문제 해결

### "Error creating build plan with Railpack" (Railway)

- **원인:** 저장소 루트에서 빌드되어 `backend/` 안의 Python이 인식되지 않음.
- **해결:** Backend 서비스 **Settings** → **Root Directory**를 `backend`로 설정한 뒤 다시 배포.
- 프로젝트를 지우고, **Empty project** → **Empty Service** 생성 → Root Directory `backend` 설정 → **Connect Repo** 순서로 다시 시도해도 됩니다.

### CORS 에러

Backend `backend/app/main.py`의 `allow_origins`에 사용 중인 Frontend 도메인을 추가합니다. Cloudflare Pages 배포별 URL(`https://xxxxx.goodpocket.pages.dev`)은 `allow_origin_regex`로 이미 허용되어 있으므로, **커스텀 도메인**을 쓰는 경우에만 해당 도메인을 `allow_origins`에 추가하면 됩니다.

### Railway "Build timed out" / "importing to docker" 후 실패

- **원인:** (1) 빌드 단계가 오래 걸리거나 (2) **이미지가 너무 커서** 푸시/임포트 단계에서 타임아웃됨 (torch + CUDA 조합 시 이미지가 수 GB).
- **해결:** Dockerfile에서 **CPU 전용 PyTorch**를 먼저 설치하도록 되어 있음 (`torch --index-url https://download.pytorch.org/whl/cpu`). Railway는 GPU가 없으므로 CPU 버전으로 충분하며, 이미지 크기가 줄어 푸시가 완료되기 쉬움. 그래도 실패하면 Railway **Project** → **Settings**에서 빌드 타임아웃을 늘리거나, 로그 끝 단계를 확인하세요.

### Railway 배포 후 바로 크래시 (ValidationError: 5 validation errors for Settings)

- **원인:** 백엔드가 필요로 하는 **환경 변수가 Railway에 설정되지 않음**. 로그에 `supabase_url`, `supabase_anon_key`, `supabase_service_role_key`, `supabase_jwt_secret`, `database_url` — Field required 가 보이면 이 경우입니다.
- **해결:** Railway **Project** → **Variables** (또는 해당 **Service** → **Variables**)에서 위 5개 변수와 `BATCH_JOB_SECRET`을 추가하세요. 값은 Supabase Dashboard (Project Settings → API, Database)에서 복사합니다. **공유 변수(Shared Variables)**를 쓰는 경우, 해당 **서비스** → **Variables** 탭에서 "Add All" 또는 개별 변수를 서비스에 연결해야 합니다. 저장 후 재배포(또는 자동 재시작)되면 앱이 기동합니다.

### Railway 크래시: `ValueError: 'db.xxx.supabase.co' does not appear to be an IPv4 or IPv6 address`

- **원인:** `DATABASE_URL`에 호스트가 대괄호로 감싸여 있는 경우(예: `postgresql://...@[db.xxx.supabase.co]:5432/...`) Python의 URL 파서가 이를 IPv6으로 간주해 검사하다 도메인 이름에서 실패합니다.
- **해결:** 백엔드 코드에서 DSN을 넘기기 전에 호스트명의 대괄호를 제거하는 정규화를 적용해 두었습니다. 최신 코드로 배포하면 해결됩니다. Railway에서 `DATABASE_URL`을 대괄호 없이 `...@db.xxx.supabase.co:5432/...` 형태로 넣어도 동작합니다.

### Railway 크래시: `OSError: [Errno 101] Network is unreachable` (로컬에서는 Supabase 연결됨)

- **원인:** Railway는 **아웃바운드 IPv6를 지원하지 않습니다**. Supabase Direct 연결은 기본적으로 IPv6로 연결을 시도하는데, Railway 네트워크에서는 해당 경로가 없어 "Network is unreachable"이 발생합니다. 로컬 PC는 IPv6 또는 이중 스택이라 잘 되고, Railway만 실패하는 이유입니다.
- **해결:** 백엔드 `app/database.py`에서 DB 연결 전에 호스트명을 **IPv4로만** DNS 조회해 DSN의 호스트를 IPv4 주소로 바꾸도록 되어 있습니다. 최신 코드로 배포하면 Railway에서도 Supabase에 연결됩니다. (Supabase 프로젝트가 Paused 상태면 복구 후 재배포하세요.)

### Railway PORT

Railway는 `PORT` 환경변수를 제공합니다. `Procfile`·`nixpacks.toml`에서 `$PORT`를 사용하므로 별도 설정 없이 동작합니다.

### Cloudflare 빌드 실패

- Root directory가 `frontend`인지 확인
- Node 버전: Cloudflare 기본 버전 사용. 필요 시 Build command에 `npx vite build` 등 명시
