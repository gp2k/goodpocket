-- =====================================================
-- Migration: Add time_added and read_status to bookmarks
-- Date: 2026-01-31
-- =====================================================

-- 1. Add new columns
ALTER TABLE bookmarks 
ADD COLUMN IF NOT EXISTS time_added TIMESTAMPTZ,
ADD COLUMN IF NOT EXISTS read_status TEXT DEFAULT 'unread';

-- 2. Add constraint for read_status
ALTER TABLE bookmarks
ADD CONSTRAINT check_read_status CHECK (read_status IN ('read', 'unread'));

-- 3. Migrate existing data
-- time_added: Set to current UTC timestamp for existing records
-- read_status: Default to 'unread'
UPDATE bookmarks 
SET time_added = NOW(),
    read_status = 'unread'
WHERE time_added IS NULL;

-- 4. Add indexes for efficient queries
CREATE INDEX IF NOT EXISTS idx_bookmarks_read_status 
    ON bookmarks(user_id, read_status);
CREATE INDEX IF NOT EXISTS idx_bookmarks_time_added 
    ON bookmarks(user_id, time_added DESC);
