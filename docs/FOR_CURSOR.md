# Cursor / AI 에이전트용 요약

이 프로젝트에서 코드 수정·배포·마이그레이션 작업 시 아래를 우선 참고하세요.

## 규칙 (Rules)

- **.cursor/rules/** 에 프로젝트·백엔드·프론트엔드 규칙이 있습니다.
  - `goodpocket-project.mdc`: 항상 적용. 스택, 클러스터=dup_groups, "Cluster N" 금지, 문서 링크.
  - `backend-python.mdc`: backend/**/*.py 작업 시.
  - `frontend-react.mdc`: frontend/**/*.ts, tsx 작업 시.

## 핵심 컨벤션

- **실행**: Backend는 venv 사용. 의존성 설치·스크립트 실행은 가상환경에서.
- **클러스터**: UI/API의 클러스터 = **dup_groups**. ID는 UUID. 라벨은 representative_bookmark 기준.
- **무의미한 라벨/태그**: "Cluster 47" 형태 사용 금지. Backend fallback은 빈 문자열, 태그는 _is_valid_tag에서 차단, Frontend는 clusterLabelDisplay()로 "그룹" 또는 숨김.
- **배포**: Backend → Railway(Root `backend`), Frontend → Cloudflare Pages(Root `frontend`). 자세한 내용은 DEPLOY.md.

## 문서 링크

- [ARCHITECTURE.md](ARCHITECTURE.md) — 데이터 모델, API, 마이그레이션
- [DEVELOPMENT.md](DEVELOPMENT.md) — 규칙 요약, 실행·테스트·배포·마이그레이션
- [DEPLOY.md](../DEPLOY.md) — 배포 절차, 환경 변수, 트러블슈팅
- [CLUSTER_COMPLEXITY_DIAGNOSIS.md](CLUSTER_COMPLEXITY_DIAGNOSIS.md) — 클러스터 복잡도 진단
