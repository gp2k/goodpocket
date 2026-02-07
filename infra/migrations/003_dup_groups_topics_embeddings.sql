-- =====================================================
-- Migration: dup_groups, topics, tags (normalized), embeddings prep
-- Depends on: 001_initial_schema.sql, 002_add_bookmark_fields.sql
-- =====================================================

-- =====================================================
-- 1. BOOKMARKS: add columns for dedup and indexing
-- =====================================================
ALTER TABLE bookmarks
ADD COLUMN IF NOT EXISTS domain TEXT,
ADD COLUMN IF NOT EXISTS fetched_at TIMESTAMPTZ,
ADD COLUMN IF NOT EXISTS summary_text TEXT,
ADD COLUMN IF NOT EXISTS content_hash TEXT,
ADD COLUMN IF NOT EXISTS simhash64 BIGINT,
ADD COLUMN IF NOT EXISTS lang TEXT;

CREATE INDEX IF NOT EXISTS idx_bookmarks_domain ON bookmarks(domain);
CREATE INDEX IF NOT EXISTS idx_bookmarks_simhash64 ON bookmarks(simhash64);

-- =====================================================
-- 2. DUP_GROUPS (one per simhash bucket per user)
-- =====================================================
CREATE TABLE IF NOT EXISTS dup_groups (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL,
    representative_bookmark_id UUID REFERENCES bookmarks(id) ON DELETE SET NULL,
    size INTEGER NOT NULL DEFAULT 0,
    simhash_bucket BIGINT NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_dup_groups_user_id ON dup_groups(user_id);
CREATE INDEX IF NOT EXISTS idx_dup_groups_simhash_bucket ON dup_groups(simhash_bucket);

-- =====================================================
-- 3. BOOKMARK_DUP_MAP (bookmark -> dup_group)
-- =====================================================
CREATE TABLE IF NOT EXISTS bookmark_dup_map (
    bookmark_id UUID NOT NULL REFERENCES bookmarks(id) ON DELETE CASCADE,
    dup_group_id UUID NOT NULL REFERENCES dup_groups(id) ON DELETE CASCADE,
    PRIMARY KEY (bookmark_id, dup_group_id)
);

CREATE INDEX IF NOT EXISTS idx_bookmark_dup_map_dup_group_id ON bookmark_dup_map(dup_group_id);
CREATE INDEX IF NOT EXISTS idx_bookmark_dup_map_bookmark_id ON bookmark_dup_map(bookmark_id);

-- =====================================================
-- 4. TAGS (normalized labels per user)
-- =====================================================
CREATE TABLE IF NOT EXISTS tags (
    id SERIAL PRIMARY KEY,
    user_id UUID NOT NULL,
    normalized_label TEXT NOT NULL,
    UNIQUE (user_id, normalized_label)
);

CREATE INDEX IF NOT EXISTS idx_tags_normalized_label ON tags(normalized_label);
CREATE INDEX IF NOT EXISTS idx_tags_user_id ON tags(user_id);

-- =====================================================
-- 5. BOOKMARK_TAGS (bookmark <-> tag with weight)
-- =====================================================
CREATE TABLE IF NOT EXISTS bookmark_tags (
    bookmark_id UUID NOT NULL REFERENCES bookmarks(id) ON DELETE CASCADE,
    tag_id INTEGER NOT NULL REFERENCES tags(id) ON DELETE CASCADE,
    weight REAL NOT NULL DEFAULT 1.0,
    PRIMARY KEY (bookmark_id, tag_id)
);

CREATE INDEX IF NOT EXISTS idx_bookmark_tags_tag_id ON bookmark_tags(tag_id);
CREATE INDEX IF NOT EXISTS idx_bookmark_tags_bookmark_id ON bookmark_tags(bookmark_id);

-- =====================================================
-- 6. TOPICS (hierarchical)
-- =====================================================
CREATE TABLE IF NOT EXISTS topics (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL,
    parent_id UUID REFERENCES topics(id) ON DELETE CASCADE,
    label TEXT NOT NULL,
    metrics_json JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_topics_user_parent ON topics(user_id, parent_id);

-- =====================================================
-- 7. DUP_GROUP_TOPICS (dup_group -> topic)
-- =====================================================
CREATE TABLE IF NOT EXISTS dup_group_topics (
    dup_group_id UUID NOT NULL REFERENCES dup_groups(id) ON DELETE CASCADE,
    topic_id UUID NOT NULL REFERENCES topics(id) ON DELETE CASCADE,
    PRIMARY KEY (dup_group_id, topic_id)
);

CREATE INDEX IF NOT EXISTS idx_dup_group_topics_topic_id ON dup_group_topics(topic_id);

-- =====================================================
-- UPDATED_AT trigger for dup_groups
-- =====================================================
CREATE TRIGGER trigger_dup_groups_updated_at
    BEFORE UPDATE ON dup_groups
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- =====================================================
-- ROW LEVEL SECURITY
-- =====================================================
ALTER TABLE dup_groups ENABLE ROW LEVEL SECURITY;
ALTER TABLE bookmark_dup_map ENABLE ROW LEVEL SECURITY;
ALTER TABLE tags ENABLE ROW LEVEL SECURITY;
ALTER TABLE bookmark_tags ENABLE ROW LEVEL SECURITY;
ALTER TABLE topics ENABLE ROW LEVEL SECURITY;
ALTER TABLE dup_group_topics ENABLE ROW LEVEL SECURITY;

-- dup_groups
CREATE POLICY "Users can view own dup_groups" ON dup_groups FOR SELECT USING (auth.uid() = user_id);
CREATE POLICY "Users can insert own dup_groups" ON dup_groups FOR INSERT WITH CHECK (auth.uid() = user_id);
CREATE POLICY "Users can update own dup_groups" ON dup_groups FOR UPDATE USING (auth.uid() = user_id);
CREATE POLICY "Users can delete own dup_groups" ON dup_groups FOR DELETE USING (auth.uid() = user_id);

-- bookmark_dup_map (via dup_groups ownership; allow if user owns the dup_group)
CREATE POLICY "Users can view own bookmark_dup_map" ON bookmark_dup_map FOR SELECT
    USING (EXISTS (SELECT 1 FROM dup_groups d WHERE d.id = dup_group_id AND d.user_id = auth.uid()));
CREATE POLICY "Users can insert own bookmark_dup_map" ON bookmark_dup_map FOR INSERT
    WITH CHECK (EXISTS (SELECT 1 FROM dup_groups d WHERE d.id = dup_group_id AND d.user_id = auth.uid()));
CREATE POLICY "Users can delete own bookmark_dup_map" ON bookmark_dup_map FOR DELETE
    USING (EXISTS (SELECT 1 FROM dup_groups d WHERE d.id = dup_group_id AND d.user_id = auth.uid()));

-- tags
CREATE POLICY "Users can view own tags" ON tags FOR SELECT USING (auth.uid() = user_id);
CREATE POLICY "Users can insert own tags" ON tags FOR INSERT WITH CHECK (auth.uid() = user_id);
CREATE POLICY "Users can update own tags" ON tags FOR UPDATE USING (auth.uid() = user_id);
CREATE POLICY "Users can delete own tags" ON tags FOR DELETE USING (auth.uid() = user_id);

-- bookmark_tags (via tags ownership)
CREATE POLICY "Users can view own bookmark_tags" ON bookmark_tags FOR SELECT
    USING (EXISTS (SELECT 1 FROM tags t WHERE t.id = tag_id AND t.user_id = auth.uid()));
CREATE POLICY "Users can insert own bookmark_tags" ON bookmark_tags FOR INSERT
    WITH CHECK (EXISTS (SELECT 1 FROM tags t WHERE t.id = tag_id AND t.user_id = auth.uid()));
CREATE POLICY "Users can update own bookmark_tags" ON bookmark_tags FOR UPDATE
    USING (EXISTS (SELECT 1 FROM tags t WHERE t.id = tag_id AND t.user_id = auth.uid()));
CREATE POLICY "Users can delete own bookmark_tags" ON bookmark_tags FOR DELETE
    USING (EXISTS (SELECT 1 FROM tags t WHERE t.id = tag_id AND t.user_id = auth.uid()));

-- topics
CREATE POLICY "Users can view own topics" ON topics FOR SELECT USING (auth.uid() = user_id);
CREATE POLICY "Users can insert own topics" ON topics FOR INSERT WITH CHECK (auth.uid() = user_id);
CREATE POLICY "Users can update own topics" ON topics FOR UPDATE USING (auth.uid() = user_id);
CREATE POLICY "Users can delete own topics" ON topics FOR DELETE USING (auth.uid() = user_id);

-- dup_group_topics (via dup_groups ownership)
CREATE POLICY "Users can view own dup_group_topics" ON dup_group_topics FOR SELECT
    USING (EXISTS (SELECT 1 FROM dup_groups d WHERE d.id = dup_group_id AND d.user_id = auth.uid()));
CREATE POLICY "Users can insert own dup_group_topics" ON dup_group_topics FOR INSERT
    WITH CHECK (EXISTS (SELECT 1 FROM dup_groups d WHERE d.id = dup_group_id AND d.user_id = auth.uid()));
CREATE POLICY "Users can delete own dup_group_topics" ON dup_group_topics FOR DELETE
    USING (EXISTS (SELECT 1 FROM dup_groups d WHERE d.id = dup_group_id AND d.user_id = auth.uid()));
