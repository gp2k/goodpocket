# Supabase 설정 가이드

## 1. 프로젝트 생성

1. [Supabase Dashboard](https://supabase.com/dashboard)에서 "New Project" 클릭
2. 프로젝트 이름, 데이터베이스 비밀번호, 리전 설정
   - 리전: Northeast Asia (ap-northeast-1) 권장 (한국 사용자)
3. "Create new project" 클릭 후 2-3분 대기

## 2. pgvector 확장 활성화

1. Dashboard > Database > Extensions
2. `vector` 검색
3. "Enable" 클릭

## 3. 스키마 마이그레이션 실행

1. Dashboard > SQL Editor
2. `infra/migrations/001_initial_schema.sql` 내용 복사/붙여넣기
3. "Run" 클릭

## 4. 환경 변수 수집

### API Settings (Settings > API)
- **Project URL**: `SUPABASE_URL`
  - 예: `https://abcdefgh.supabase.co`
- **anon public key**: `SUPABASE_ANON_KEY`
- **service_role key**: `SUPABASE_SERVICE_ROLE_KEY` (비밀 유지!)

### Database (Settings > Database)
- **Connection string**: `DATABASE_URL`
  - URI 형식 선택
  - `[YOUR-PASSWORD]`를 실제 비밀번호로 교체
  - 예: `postgresql://postgres:password@db.abcdefgh.supabase.co:5432/postgres`

### JWT (Settings > API > JWT Settings)
- **JWT Secret**: `SUPABASE_JWT_SECRET`

## 5. Auth 설정

### 이메일 인증 (Settings > Auth > Email Auth)
- "Enable Email Signup" 활성화
- "Confirm email" 옵션 설정 (선택)

### 리다이렉트 URL (Settings > Auth > URL Configuration)
- Site URL: 프론트엔드 URL (예: `https://goodpocket.pages.dev`)
- Redirect URLs에 추가:
  - `http://localhost:5173` (개발용)
  - `https://goodpocket.pages.dev` (프로덕션)

## 6. RLS 확인

마이그레이션 스크립트에 RLS 정책이 포함되어 있습니다.
Dashboard > Authentication > Policies에서 확인:

- `bookmarks` 테이블: 사용자별 CRUD 정책
- `clusters` 테이블: 사용자별 CRUD 정책

## 7. 배치 작업을 위한 Service Role

배치 작업(임베딩/클러스터링)은 `SUPABASE_SERVICE_ROLE_KEY`를 사용합니다.
이 키는 RLS를 우회하므로 절대 클라이언트에 노출하지 마세요.

## 문제 해결

### pgvector 설치 오류
Supabase Free tier에서는 pgvector가 기본 지원됩니다.
Extensions에서 보이지 않으면 프로젝트를 새로 만들어보세요.

### RLS 정책 오류
```sql
-- 정책 삭제 후 재생성
DROP POLICY IF EXISTS "Users can view own bookmarks" ON bookmarks;
-- ... 다른 정책들도 삭제 후 재생성
```

### 연결 문제
- Database Password 확인
- Connection pooling 모드 확인 (Transaction 권장)
- SSL 모드: require
