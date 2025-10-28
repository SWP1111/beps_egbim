-- Migration: Content Manager Refactoring
-- Description: Add tables for pending content, archived content, and page additionals
-- Date: 2025-01-24

-- ==================================================
-- Table: page_additionals
-- Purpose: Track additional content files for pages
-- ==================================================
CREATE TABLE IF NOT EXISTS page_additionals (
    id SERIAL PRIMARY KEY,
    page_id INTEGER NOT NULL REFERENCES content_rel_pages(id),
    filename VARCHAR(255) NOT NULL,
    object_key VARCHAR(500) NOT NULL,
    file_extension VARCHAR(10) NOT NULL,
    content_number INTEGER NOT NULL,
    file_size BIGINT DEFAULT 0,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    is_deleted BOOLEAN DEFAULT FALSE,
    CONSTRAINT uq_page_content_number UNIQUE (page_id, content_number)
);

-- Create indexes for page_additionals
CREATE INDEX IF NOT EXISTS idx_page_additionals_page_id ON page_additionals(page_id);
CREATE INDEX IF NOT EXISTS idx_page_additionals_is_deleted ON page_additionals(is_deleted);

-- ==================================================
-- Table: pending_content
-- Purpose: Track pending uploads awaiting approval
-- ==================================================
CREATE TABLE IF NOT EXISTS pending_content (
    id SERIAL PRIMARY KEY,
    content_type VARCHAR(20) NOT NULL CHECK (content_type IN ('page', 'additional')),
    page_id INTEGER NOT NULL REFERENCES content_rel_pages(id),
    additional_id INTEGER REFERENCES page_additionals(id),
    object_key VARCHAR(500) NOT NULL,
    filename VARCHAR(255) NOT NULL,
    file_size BIGINT DEFAULT 0,
    uploaded_by TEXT NOT NULL REFERENCES users(id),
    uploaded_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Create indexes for pending_content
CREATE INDEX IF NOT EXISTS idx_pending_content_page_id ON pending_content(page_id);
CREATE INDEX IF NOT EXISTS idx_pending_content_additional_id ON pending_content(additional_id);
CREATE INDEX IF NOT EXISTS idx_pending_content_uploaded_by ON pending_content(uploaded_by);
CREATE INDEX IF NOT EXISTS idx_pending_content_type ON pending_content(content_type);

-- ==================================================
-- Table: archived_content
-- Purpose: Track archived versions (old content)
-- ==================================================
CREATE TABLE IF NOT EXISTS archived_content (
    id SERIAL PRIMARY KEY,
    content_type VARCHAR(20) NOT NULL CHECK (content_type IN ('page', 'additional')),
    original_page_id INTEGER NOT NULL REFERENCES content_rel_pages(id),
    original_additional_id INTEGER REFERENCES page_additionals(id),
    object_key VARCHAR(500) NOT NULL,
    archived_filename VARCHAR(255) NOT NULL,
    file_size BIGINT DEFAULT 0,
    archived_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    archived_by TEXT NOT NULL REFERENCES users(id)
);

-- Create indexes for archived_content
CREATE INDEX IF NOT EXISTS idx_archived_content_page_id ON archived_content(original_page_id);
CREATE INDEX IF NOT EXISTS idx_archived_content_additional_id ON archived_content(original_additional_id);
CREATE INDEX IF NOT EXISTS idx_archived_content_archived_by ON archived_content(archived_by);
CREATE INDEX IF NOT EXISTS idx_archived_content_archived_at ON archived_content(archived_at);

-- ==================================================
-- Comments for documentation
-- ==================================================
COMMENT ON TABLE page_additionals IS 'Additional content files for pages, following {page_prefix}_{number}.{ext} naming convention';
COMMENT ON TABLE pending_content IS 'Pending content uploads awaiting 책임자 approval';
COMMENT ON TABLE archived_content IS 'Archived versions of content (old versions before updates)';

COMMENT ON COLUMN page_additionals.content_number IS 'The sequence number in filename pattern {page_prefix}_{content_number}.{ext}';
COMMENT ON COLUMN pending_content.content_type IS 'Type of content: page (main page image) or additional (extra content)';
COMMENT ON COLUMN archived_content.archived_by IS '책임자 (category manager) who approved the update';

-- ==================================================
-- Rollback Script (commented out - uncomment to rollback)
-- ==================================================
-- DROP TABLE IF EXISTS archived_content CASCADE;
-- DROP TABLE IF EXISTS pending_content CASCADE;
-- DROP TABLE IF EXISTS page_additionals CASCADE;
