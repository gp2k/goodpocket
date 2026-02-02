-- =====================================================
-- Bookmark Clustering MVP - Initial Database Schema
-- Supabase Postgres with pgvector extension
-- =====================================================

-- Enable pgvector extension for vector embeddings
CREATE EXTENSION IF NOT EXISTS vector;

-- =====================================================
-- BOOKMARKS TABLE
-- =====================================================
CREATE TABLE bookmarks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL,
    url TEXT NOT NULL,
    canonical_url TEXT,
    title TEXT,
    summary TEXT,
    extracted_text_excerpt TEXT,  -- Store first 2000 chars only
    tags TEXT[] DEFAULT '{}',
    embedding vector(384),  -- all-MiniLM-L6-v2 produces 384-dim vectors
    status TEXT DEFAULT 'pending_embedding' 
        CHECK (status IN ('pending_embedding', 'embedded', 'failed')),
    cluster_id INTEGER,
    cluster_label TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    embedded_at TIMESTAMPTZ,
    
    -- Prevent duplicate URLs per user
    CONSTRAINT unique_user_url UNIQUE (user_id, url)
);

-- Indexes for common queries
CREATE INDEX idx_bookmarks_user_id ON bookmarks(user_id);
CREATE INDEX idx_bookmarks_status ON bookmarks(status);
CREATE INDEX idx_bookmarks_cluster ON bookmarks(user_id, cluster_id);
CREATE INDEX idx_bookmarks_created ON bookmarks(user_id, created_at DESC);
CREATE INDEX idx_bookmarks_tags ON bookmarks USING GIN(tags);

-- HNSW vector index for cosine similarity search
-- m=16: max connections per node, ef_construction=64: build-time search width
CREATE INDEX idx_bookmarks_embedding ON bookmarks 
    USING hnsw (embedding vector_cosine_ops)
    WITH (m = 16, ef_construction = 64);

-- =====================================================
-- CLUSTERS TABLE (per-user cluster metadata)
-- =====================================================
CREATE TABLE clusters (
    id SERIAL PRIMARY KEY,
    user_id UUID NOT NULL,
    cluster_id INTEGER NOT NULL,  -- Cluster number within user's bookmarks
    label TEXT,  -- Top tags as cluster label (e.g., "python, machine_learning, tutorial")
    size INTEGER DEFAULT 0,
    cluster_version TIMESTAMPTZ DEFAULT NOW(),  -- When clustering was last run
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    
    CONSTRAINT unique_user_cluster UNIQUE (user_id, cluster_id)
);

CREATE INDEX idx_clusters_user ON clusters(user_id);

-- =====================================================
-- UPDATED_AT TRIGGER FUNCTION
-- =====================================================
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Apply trigger to bookmarks
CREATE TRIGGER trigger_bookmarks_updated_at
    BEFORE UPDATE ON bookmarks
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- Apply trigger to clusters
CREATE TRIGGER trigger_clusters_updated_at
    BEFORE UPDATE ON clusters
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- =====================================================
-- ROW LEVEL SECURITY (RLS) POLICIES
-- Ensures users can only access their own data
-- =====================================================

-- Enable RLS on tables
ALTER TABLE bookmarks ENABLE ROW LEVEL SECURITY;
ALTER TABLE clusters ENABLE ROW LEVEL SECURITY;

-- Bookmarks policies
CREATE POLICY "Users can view own bookmarks" ON bookmarks
    FOR SELECT USING (auth.uid() = user_id);

CREATE POLICY "Users can insert own bookmarks" ON bookmarks
    FOR INSERT WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Users can update own bookmarks" ON bookmarks
    FOR UPDATE USING (auth.uid() = user_id);

CREATE POLICY "Users can delete own bookmarks" ON bookmarks
    FOR DELETE USING (auth.uid() = user_id);

-- Clusters policies
CREATE POLICY "Users can view own clusters" ON clusters
    FOR SELECT USING (auth.uid() = user_id);

CREATE POLICY "Users can insert own clusters" ON clusters
    FOR INSERT WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Users can update own clusters" ON clusters
    FOR UPDATE USING (auth.uid() = user_id);

CREATE POLICY "Users can delete own clusters" ON clusters
    FOR DELETE USING (auth.uid() = user_id);

-- =====================================================
-- SERVICE ROLE BYPASS (for batch jobs)
-- The service role key bypasses RLS by default in Supabase
-- =====================================================

-- Grant service role full access (this is default in Supabase)
-- GRANT ALL ON bookmarks TO service_role;
-- GRANT ALL ON clusters TO service_role;
