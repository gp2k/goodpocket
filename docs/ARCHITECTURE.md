# GoodPocket 아키텍처

## 개요

- **Frontend**: Vite + React + TypeScript (Cloudflare Pages 배포)
- **Backend**: FastAPI (Railway 배포, Root Directory: `backend`)
- **DB / Auth**: Supabase (PostgreSQL, Auth)

## 클러스터 데이터 모델

### 현재 사용 중: dup_groups

- **클러스터(UI/API)**는 **dup_groups** 테이블을 의미함.
- simhash로 "거의 같은 문서"를 묶은 그룹. ID는 **UUID**.
- **bookmark_dup_map**: 북마크 ↔ dup_group 다대일 매핑.
- 클러스터 라벨: 해당 dup_group의 **representative_bookmark**의 title 또는 domain.

### API

- `GET /api/clusters`: 쿼리 파라미터 `limit`(기본 40, 최대 100), `min_size`(기본 1). `ORDER BY size DESC` 후 LIMIT 적용.
- `GET /api/clusters/{id}`: dup_group 상세 + bookmark_dup_map으로 소속 북마크 목록.

### 레거시(배치 전용)

- **bookmarks.cluster_id**, **bookmarks.cluster_label**: HDBSCAN 배치 결과 저장용. "Cluster N" 형태 라벨은 사용하지 않음(빈 문자열 또는 의미 있는 라벨만).
- **clusters** 테이블: 사용자별 HDBSCAN 클러스터 메타. 목록/상세 API에서는 사용하지 않음.

## 주제(topics) 구조 (미사용)

- **topics**: 계층 구조(예: root → 도메인별). 사용자별.
- **dup_group_topics**: dup_group ↔ topic 연결.
- 마이그레이션 스크립트가 채우나, 현재 API/UI에서는 노출하지 않음. 추후 "주제 → 클러스터" 2단계 뷰에 활용 예정.

## 태그

- **tags**: 정규화된 라벨(사용자별 unique).
- **bookmark_tags**: 북마크 ↔ 태그, weight.
- "Cluster N" 패턴(`cluster\s*_?\s*\d+`, 대소문자 무시) 태그는 생성/저장하지 않음(tag_generator, 마이그레이션 스크립트에서 필터).

## 마이그레이션

- **003 스키마**: `infra/migrations/003_dup_groups_topics_embeddings.sql` — bookmarks 확장, dup_groups, bookmark_dup_map, tags, bookmark_tags, topics, dup_group_topics, RLS.
- **데이터 백필**: `backend/scripts/migrate_to_dup_topics.py` — 컬럼 백필 → tags/bookmark_tags → dup_groups/bookmark_dup_map → topics/dup_group_topics. `--resume`, `--user-id`, `--chunk-size`, `--dry-run` 지원.
- 진행 상황 확인: `backend/scripts/check_migration_progress.py`.

## 관련 문서

- 클러스터 복잡도 진단 및 개선 배경: [CLUSTER_COMPLEXITY_DIAGNOSIS.md](CLUSTER_COMPLEXITY_DIAGNOSIS.md)
- 배포: [DEPLOY.md](../DEPLOY.md)
- 개발/기여: [DEVELOPMENT.md](DEVELOPMENT.md)
