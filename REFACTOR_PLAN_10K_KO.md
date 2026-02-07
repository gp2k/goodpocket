# 10k+ 북마크 규모 대응 클러스터링·시각화 리팩터링 플랜

## 적용 가능 여부

**현재 goodpocket 프로젝트 구조에 그대로 적용 가능합니다.**

- DB: `infra/migrations/001_initial_schema.sql`, `002_add_bookmark_fields.sql` 존재
- 백엔드: `batch_processor.py`, `clustering.py`, `embedding.py`, `tag_generator.py`, `content_extractor.py`, 라우터·스키마 경로 일치
- 프론트: `ClusterMindmap.tsx`, `Clusters.tsx`, `api.ts` 등 플랜에서 언급한 경로와 동일
- 테스트: `test_tag_normalization.py` 존재

---

## 현재 상태 정리

**DB** (`infra/migrations/001_initial_schema.sql`, `002_add_bookmark_fields.sql`)

- `bookmarks`: id, user_id, url, canonical_url, title, summary, extracted_text_excerpt(2k), tags(TEXT[]), embedding vector(384), status, cluster_id, cluster_label, created_at, updated_at, time_added, read_status. (user_id, url) 유니크.
- `clusters`: id, user_id, cluster_id, label, size, cluster_version, updated_at. (user_id, cluster_id)당 한 행.
- `bookmarks(embedding)` HNSW 인덱스, tags GIN, user_id·status·cluster_id·time_added 인덱스 있음.

**백엔드**

- `batch_processor.py`: `pending_embedding` 북마크를 50개 단위로 처리; 임베딩 생성 후 **전체** 사용자 임베딩에 대해 UMAP+HDBSCAN(또는 코사인 임계)으로 **전역** 클러스터링 후 cluster_id/cluster_label 기록, clusters 업서트. simhash·중복 그룹 없음.
- `clustering.py`: UMAP(15차원, 10 neighbors) + HDBSCAN(min_cluster_size 설정); `embedding.py` 384차원 all-MiniLM-L6-v2; `tag_generator.py` Kiwi(한국어)+YAKE(영어), 정규화·중복 제거, DB에 가중치 없음.
- `content_extractor.py`: Trafilatura/readability, title·text·summary 반환(길이 제한 없음; DB excerpt 2k).
- 중복 그룹·토픽 계층·“이 ID들만 인덱싱” API 없음.

**프론트엔드**

- `ClusterMindmap.tsx`: D3 force 시뮬레이션(forceSimulation, forceLink, forceManyBody 등)으로 루트·클러스터·북마크 노드와 링크 구성, SVG 렌더. 10k 규모에는 부적합.
- `Clusters.tsx`: 리스트/마인드맵 전환; 클러스터 목록 로드 후 ID별 상세 로드.
- `api.ts`: `clustersApi.list()`, `clustersApi.get(clusterId)`; 트리·중복그룹 API 없음.

**제약**

- Railway Free: 1 vCPU, 0.5GB RAM — 10k 임베딩 한 번에 로드 금지, 청크 단위 처리.
- Supabase: Postgres + pgvector; 저장량 절약(요약·인덱스 위주, 원문 전체 DB 저장 지양).
- 리팩터링 중에도 서비스 유지: 스키마·엔드포인트는 추가 우선, 새 시각화 준비 후 전환.

---

## A) DB 스키마 마이그레이션

**새 마이그레이션 파일:** `infra/migrations/003_dup_groups_topics_embeddings.sql`

**추가할 테이블/컬럼 (RLS용으로 모두 `user_id` 포함):**

1. **bookmarks (기존 테이블 확장)**
   - 추가 컬럼: `domain TEXT`, `published_at TIMESTAMPTZ`, `fetched_at TIMESTAMPTZ`, `summary_text TEXT`(앱에서 약 2KB 제한), `content_hash TEXT`, `simhash64 BIGINT`, `lang TEXT`. 기존 `embedding`은 당분간 유지; 이후 선택적으로 `embeddings` 테이블로 이전 가능.
   - 인덱스: `bookmarks(domain)`, `bookmarks(simhash64)`(중복 그룹용).
2. **dup_groups**
   - `id UUID PRIMARY KEY`, `user_id UUID NOT NULL`, `representative_bookmark_id UUID REFERENCES bookmarks(id)`, `size INT`, `simhash_bucket BIGINT`(또는 대표 북마크 simhash64), `created_at`, `updated_at`.
   - 인덱스: `dup_groups(user_id)`, `dup_groups(simhash_bucket)`.
3. **bookmark_dup_map**
   - `bookmark_id UUID`, `dup_group_id UUID`; 복합 PK; `dup_group_id`, `bookmark_id` 인덱스.
4. **tags** (정규화된 라벨)
   - `id SERIAL PRIMARY KEY`, `user_id UUID`, `normalized_label TEXT` 사용자별(또는 전역) UNIQUE. `normalized_label` 인덱스.
5. **bookmark_tags**
   - `bookmark_id UUID`, `tag_id INT`, `weight REAL`. `tag_id`, `bookmark_id` 인덱스.
6. **topics** (계층형)
   - `id UUID PRIMARY KEY`, `user_id UUID`, `parent_id UUID REFERENCES topics(id)`, `label TEXT`, `metrics_json JSONB`, `created_at`. `(user_id, parent_id)` 인덱스.
7. **bookmark_topics** 또는 **dup_group_topics**
   - `(bookmark_id, topic_id)` 또는 `(dup_group_id, topic_id)`; `topic_id` 인덱스.
8. **embeddings** (선택; 초기에는 bookmarks.embedding 유지 가능)
   - `id UUID`, `user_id UUID`, `bookmark_id UUID` 또는 `dup_group_id UUID`, `embedding vector(384)`, `model TEXT`, `created_at`. `embedding`에 HNSW/IVFFlat. 북마크당 한 행(또는 대표만 임베딩 시 dup_group당 한 행).

**RLS:** 새 테이블 모두 RLS 활성화, bookmarks와 동일하게 “본인 행만 CRUD” 정책. 배치 작업은 서비스 롤 사용.

**전달:** 단일 SQL 파일 + README 또는 `infra/supabase_setup.md`에 001 → 002 → 003 순서로 Supabase SQL 에디터/CLI 실행 안내.

---

## B) 백엔드 리팩터링

**신규 모듈:** `backend/app/services/dedup.py`

- 정규화된 텍스트로 Simhash64 계산(simhash 라이브러리 또는 단순 64비트 단어 shingle 해시). 단위 테스트: 거의 동일한 두 텍스트 → 동일/가까운 simhash 버킷.
- simhash 버킷(동일 또는 해밍 거리 ≤3)으로 북마크 그룹화; dup_groups·bookmark_dup_map 생성; 대표 = 첫 번째 또는 domain/title 기준 “중심” 북마크.

**신규 모듈:** `backend/app/routers/index.py`

- **POST /index/bookmarks**
  - Body: `{ "bookmark_ids": [uuid, ...] | "urls": [...], "chunk_size": 50 }`.
  - 동작: ID(또는 URL→id)별로 청크 단위 처리. 필요 시 콘텐츠 수집(기존 content_extractor), 텍스트 정규화, 요약(~1–2KB), simhash64, dup_group 할당/갱신(union-find 또는 대표), tag_generator로 태그 추출(Kiwi+YAKE 유지), **가중치** 부여(예: TF 또는 1.0/top_n), 정규화 후 tags·bookmark_tags 업서트, 임베딩 생성·저장(bookmarks.embedding 또는 embeddings), bookmarks·dup_groups·bookmark_dup_map 업서트. 전부 사용자 단위; 전역 풀스캔 없음.
- **POST /index/rebuild_topics**
  - Body: `{ "scope": "all" | "date_range" | "dup_group_ids", "from": "", "to": "", "dup_group_ids": [] }`.
  - 동작: 2–4단계 토픽 트리 구성. 옵션 A: domain → 태그 클러스터 → dup_groups(경량). 옵션 B: 리소스 허용 시 대표 dup_groups만 UMAP+HDBSCAN(소규모). 각 토픽 노드: `metrics_json` = doc_count, dup_group_count, dup_rate, top_tags, domain_entropy, recency. topics + 매핑 테이블에 기록. 청크 처리 및 필요 시 “대표만” 모드로 메모리 제한 유지.

**신규 모듈:** `backend/app/routers/viz.py`

- **GET /viz/tree**
  - Sunburst/Icicle용 집계 토픽 트리: `{ id, label, metrics, children[] }`. 북마크 목록 없음; 사전 계산 트리 또는 온더플라이 집계. 루트는 페이지네이션 없음; 깊이 제한(예: 3).
- **GET /viz/node/:topicId**
  - 응답: 상위 태그·도메인, 대표 dup_groups, **페이지네이션** 북마크 목록(page, page_size).
- **GET /viz/dup_group/:id**
  - 응답: 대표 북마크, 멤버 목록(페이지네이션), 태그, 유사도 통계.

**캐싱:** 사전 계산 트리 스냅샷을 DB(예: topic_snapshots 테이블, user_id, jsonb, updated_at) 또는 TTL 인메모리 캐시에 저장; rebuild_topics 시 갱신. `/viz/tree`에서 매 요청 재계산 방지.

**공통:** 모든 목록 엔드포인트 페이지네이션(page, page_size). 10k 행 한 번에 메모리 로드 금지. 단위 테스트: simhash 그룹(거의 중복 두 건 동일 그룹), 태그 정규화(기존 test_tag_normalization 활용), API 페이지네이션(예: `/viz/node/:id` 올바른 페이지 반환).

**설정:** 필요 시 `index_chunk_size`, `topic_rebuild_representatives_only`(Railway 기본 true) 추가.

---

## C) 프론트엔드 리팩터링

**주 시각화:** 방사형 노드-링크 대신 Zoomable Sunburst(또는 Icicle).

- 새 컴포넌트: `TopicSunburst.tsx`(또는 `TopicIcicle.tsx`), **d3-hierarchy**(`d3.hierarchy`, `d3.partition` 또는 arc 레이아웃) 사용. 데이터: `GET /viz/tree`.
- 노드 클릭 시: `GET /viz/node/:topicId` 호출 후 **사이드 패널**에 상위 태그·도메인, 대표 dup_groups, 페이지네이션 북마크 목록 표시; “중복 접기” 토글(대표만 표시).
- 점진적 공개: 기본 깊이 2–3; 줌/확장 시 더 깊은 자식은 백엔드 지원 시 lazy-load(또는 트리 한 번 로드 후 렌더 깊이만 제한).

**중복 인사이트 UI:** 사이드 패널에 dup_rate, 큰 dup_groups, 대표 제목·상위 태그; 필터: 도메인, 기간, 태그 포함/제외, 최소 dup_group 크기(백엔드 쿼리 파라미터).

**선택적 노드-링크 서브 뷰:** 특정 토픽 또는 검색 결과에 한해 `ClusterMindmap.tsx`(또는 축소판) 유지, **≤1500개**일 때만. 엣지 = top-k 최근접 이웃(k≤5) 또는 유사도 임계. 성능 필요 시에만 WebGL(예: sigma.js); 아니면 현재 D3 force + 노드 수 상한(예: 500), “클러스터로 줌”으로 범위 축소.

**성능:** 10k DOM 라벨 금지. Sunburst/Icicle은 캔버스 또는 SVG + 호 너비 임계로 라벨 표시; 툴팁/호버로 상세. 10k 라벨 단일 리스트 DOM 금지.

**라우팅/API:** `api.ts`에 `vizApi.tree()`, `vizApi.node(topicId)`, `vizApi.dupGroup(id)` 추가. Clusters 페이지 또는 새 “인사이트” 페이지에서 TopicSunburst + 사이드 패널; 범위가 작을 때만 “그래프” 탭에서 노드-링크.

---

## D) 데이터 마이그레이션 스크립트

**스크립트:** `backend/scripts/migrate_to_dup_topics.py`(또는 `infra/`).

- 기존 bookmarks(및 clusters)를 DB에서 청크(예: 사용자당 500)로 읽기.
- 북마크별: summary/title로 simhash, 필요 시 content_hash 계산; summary_text, domain(URL에서), fetched_at 백필; 태그 추출 후 bookmark_tags/tags 채우기; 임베딩 존재 확인(없으면 인덱스 잡이 채우도록 스킵 가능).
- simhash 버킷 그룹으로 dup_groups·bookmark_dup_map 구성.
- 초기 토픽 트리(domain → 태그 클러스터 → dup_groups) 구성 후 topics + 매핑 테이블 기록.
- **재개 가능:** 마지막 처리 위치(user_id, bookmark_id 또는 타임스탬프) 체크포인트; 이미 처리된 것은 스킵.
- **멱등:** dup_groups/bookmark_dup_map/topics 업서트로 재실행 시 중복 없음; 청크 단위 안전 실행.

---

## E) 문서화

**README 및 DEPLOY.md(필요 시):**

- 로컬 개발: Supabase 키, Railway env(기존); 새 env(예: index 엔드포인트 인증) 추가 시 명시.
- 마이그레이션 실행: Supabase에서 `001_initial_schema.sql`, `002_add_bookmark_fields.sql`, `003_dup_groups_topics_embeddings.sql` 순서 실행.
- 인덱싱 실행: ID 목록 또는 URL로 `POST /index/bookmarks`; 선택적으로 이후 `POST /index/rebuild_topics`.
- 새 시각화 모델: TopicTree(계층) + DuplicateGroups; “왜 이렇게 하면 스케일되는지” 섹션(집계 개요, 점진적 공개, 중복을 일급 개념으로).

---

## 구현 순서 (최소 변경·단계적 적용)

1. **DB 마이그레이션** — 003 마이그레이션 추가; 기존 bookmarks/clusters 유지; 새 컬럼 nullable 또는 백필.
2. **백엔드: dedup + 인덱싱** — Python에서 simhash + dup_groups 구현; POST /index/bookmarks(증분); POST /index/rebuild_topics(청크, 선택적 representatives-only).
3. **백엔드: viz API** — GET /viz/tree, /viz/node/:id, /viz/dup_group/:id, 페이지네이션·캐싱.
4. **프론트: Sunburst/Icicle** — 새 컴포넌트 + 사이드 패널(새 API 사용); Clusters 페이지 기본을 새 뷰로, “리스트”·선택적 “그래프”(노드 수 제한) 유지.
5. **데이터 마이그레이션 스크립트** — 기존 데이터에 simhash·dup_groups·태그·토픽 백필; 재개 가능·멱등.
6. **문서** — README + 마이그레이션 런북 + “Why this scales”.

**선택적 후속:** embedding을 별도 `embeddings` 테이블로 이전; UMAP 2D + hexbin 엔드포인트로 선택적 맵 뷰; 1.5k 노드에서도 D3 force가 느리면 WebGL 노드-링크(sigma.js) 검토.
