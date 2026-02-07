# GoodPocket 아키텍처

## 개요

- **Frontend**: Vite + React + TypeScript (Cloudflare Pages 배포)
- **Backend**: FastAPI (Railway 배포, Root Directory: `backend`)
- **DB / Auth**: Supabase (PostgreSQL, Auth)

## 클러스터 데이터 모델

### 현재 사용 중: 밀도 기반 (HDBSCAN)

- **클러스터(UI/API)**는 **clusters** 테이블 + **bookmarks.cluster_id** 기반.
- 임베딩으로 HDBSCAN(UMAP 차원 축소 후) 실행, 배치 작업에서 **clusters** 테이블과 **bookmarks.cluster_id**·**cluster_label**에 저장.
- 클러스터 ID는 **clusters.id**(SERIAL)를 문자열로 노출. 라벨은 클러스터 내 북마크 태그 빈도 상위 N개로 생성.

### API

- `GET /api/clusters`: 쿼리 파라미터 `limit`(기본 40, 최대 100), `min_size`(기본 1). clusters 테이블 기준 `ORDER BY size DESC` 후 LIMIT.
- `GET /api/clusters/{id}`: clusters.id(SERIAL)로 해당 클러스터 조회 후, bookmarks에서 user_id + cluster_id로 소속 북마크 목록 반환.

### 레거시/마이그레이션용 (UI 미노출)

- **dup_groups**, **bookmark_dup_map**: simhash 기반 중복 그룹. 마이그레이션 스크립트가 채우며, 현재 API/UI에서는 사용하지 않음.
- **topics**, **dup_group_topics**: 태그 기반 계층. 마이그레이션 스크립트가 채우나, 현재 API/UI에서는 노출하지 않음.

## 태그

- **tags**: 정규화된 라벨(사용자별 unique).
- **bookmark_tags**: 북마크 ↔ 태그, weight.
- "Cluster N" 패턴(`cluster\s*_?\s*\d+`, 대소문자 무시) 태그는 생성/저장하지 않음(tag_generator, 마이그레이션 스크립트에서 필터).

## 마이그레이션

- **003 스키마**: `infra/migrations/003_dup_groups_topics_embeddings.sql` — bookmarks 확장, dup_groups, bookmark_dup_map, tags, bookmark_tags, topics, dup_group_topics, RLS.
- **데이터 백필**: `backend/scripts/migrate_to_dup_topics.py` — 컬럼 백필 → tags/bookmark_tags → dup_groups/bookmark_dup_map → topics/dup_group_topics, bookmarks.tags 동기화. `--resume`, `--user-id`, `--chunk-size`, `--dry-run` 지원.
- 진행 상황 확인: `backend/scripts/check_migration_progress.py`.

## 관련 문서

- 클러스터 복잡도 진단 및 개선 배경: [CLUSTER_COMPLEXITY_DIAGNOSIS.md](CLUSTER_COMPLEXITY_DIAGNOSIS.md)
- 배포: [DEPLOY.md](../DEPLOY.md)
- 개발/기여: [DEVELOPMENT.md](DEVELOPMENT.md)
