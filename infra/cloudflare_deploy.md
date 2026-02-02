# Cloudflare Pages 배포 가이드

## 1. 사전 준비

- Cloudflare 계정
- Wrangler CLI 설치: `npm install -g wrangler`
- Cloudflare 로그인: `wrangler login`

## 2. 빌드

```bash
cd frontend

# 의존성 설치
npm install

# 프로덕션 빌드
npm run build
```

## 3. 배포

### 방법 1: Wrangler CLI

```bash
# 첫 배포 시 프로젝트 생성됨
npx wrangler pages deploy dist --project-name goodpocket

# 프로덕션 배포
npx wrangler pages deploy dist --project-name goodpocket --branch main
```

### 방법 2: Cloudflare Dashboard

1. Cloudflare Dashboard > Pages
2. "Create a project" 클릭
3. "Direct Upload" 선택
4. `frontend/dist` 폴더 업로드
5. 프로젝트 이름 설정 후 배포

### 방법 3: Git 연동

1. GitHub/GitLab 저장소 연결
2. Build settings:
   - Framework preset: None
   - Build command: `cd frontend && npm install && npm run build`
   - Build output directory: `frontend/dist`

## 4. 환경 변수 설정

Cloudflare Dashboard > Pages > 프로젝트 > Settings > Environment variables

### Production 환경변수:
```
VITE_SUPABASE_URL=https://xxx.supabase.co
VITE_SUPABASE_ANON_KEY=xxx
VITE_API_URL=https://goodpocket-api-xxx.run.app
```

### Preview 환경변수 (개발용):
```
VITE_SUPABASE_URL=https://xxx.supabase.co
VITE_SUPABASE_ANON_KEY=xxx
VITE_API_URL=https://goodpocket-api-xxx.run.app
```

**중요**: 환경변수 설정 후 재배포 필요!

## 5. 커스텀 도메인 (선택)

1. Pages > 프로젝트 > Custom domains
2. "Set up a custom domain" 클릭
3. 도메인 입력 (예: `goodpocket.example.com`)
4. DNS 설정 안내에 따라 CNAME 레코드 추가

## 6. CORS 설정

Cloud Run 백엔드에서 Cloudflare Pages 도메인 허용:

```python
# backend/app/main.py
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "https://goodpocket.pages.dev",  # Cloudflare Pages 기본 도메인
        "https://your-custom-domain.com",  # 커스텀 도메인
    ],
    ...
)
```

## 7. 확인

배포 후 확인사항:

1. 메인 페이지 로드 확인
2. 로그인 기능 테스트
3. 북마크 저장 테스트
4. 클러스터 페이지 확인

## 문제 해결

### 빌드 실패
- Node.js 버전 확인 (18+ 권장)
- `package-lock.json` 커밋 여부 확인

### API 연결 실패
- CORS 설정 확인
- 환경변수 올바른지 확인
- Cloud Run 서비스 상태 확인

### 환경변수 미적용
- Vite는 빌드 시점에 환경변수를 주입
- 환경변수 변경 후 반드시 재배포

### 404 에러 (SPA 라우팅)
Cloudflare Pages는 기본적으로 SPA 라우팅 지원.
문제 시 `_redirects` 파일 생성:

```
# frontend/public/_redirects
/*    /index.html   200
```
