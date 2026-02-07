# 개발 및 기여 가이드

## Cursor 규칙

프로젝트에는 `.cursor/rules/` 아래 규칙이 있어 AI/개발 시 참고됩니다.

| 파일 | 적용 범위 | 내용 |
|------|------------|------|
| goodpocket-project.mdc | 항상 | 스택, 배포, 클러스터=dup_groups, 무의미한 "Cluster N" 금지, 문서 링크 |
| backend-python.mdc | backend/**/*.py | venv, 클러스터/라벨/태그 컨벤션, DB/마이그레이션 |
| frontend-react.mdc | frontend/**/*.ts, tsx | clustersApi.list(limit), cluster_label 표시, 스택 |

## 로컬 실행

### Backend

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
# .env 설정 (copy .env.example .env)
uvicorn app.main:app --reload --port 8000
```

### Frontend

```powershell
cd frontend
npm install
# .env 설정
npm run dev
```

## 테스트

```powershell
cd backend
.\.venv\Scripts\Activate.ps1
pytest -v
```

## 배포

- **백엔드**: GitHub `main` 푸시 시 Railway 자동 배포. Root Directory: `backend`.
- **프론트엔드**: `main` 푸시 시 Cloudflare Pages 자동 배포. Root: `frontend`.
- 환경 변수·설정: [DEPLOY.md](../DEPLOY.md) 참고.

## DB 마이그레이션

1. Supabase SQL Editor에서 `001` → `002` → `003` 순서로 마이그레이션 실행.
2. 003 적용 후 데이터 백필(선택):

   ```powershell
   cd backend
   .\.venv\Scripts\Activate.ps1
   python scripts/migrate_to_dup_topics.py --resume
   ```

   옵션: `--user-id UUID`, `--chunk-size N`, `--dry-run`.
3. 진행 상황: `python scripts/check_migration_progress.py`.

## 문서 목록

- [README.md](../README.md) — 프로젝트 소개, 로컬 설정, API 요약
- [DEPLOY.md](../DEPLOY.md) — 배포(Railway, Cloudflare), 환경 변수, 트러블슈팅
- [docs/ARCHITECTURE.md](ARCHITECTURE.md) — 데이터 모델, 클러스터(dup_groups), topics, 마이그레이션
- [docs/CLUSTER_COMPLEXITY_DIAGNOSIS.md](CLUSTER_COMPLEXITY_DIAGNOSIS.md) — 클러스터 복잡도 원인 및 개선 방향
- [docs/DEVELOPMENT.md](DEVELOPMENT.md) — 이 문서 (규칙, 실행, 테스트, 배포, 마이그레이션)
