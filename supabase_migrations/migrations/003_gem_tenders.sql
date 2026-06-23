-- supabase_migrations/migrations/003_gem_tenders.sql

-- Main table for GeM tenders
CREATE TABLE IF NOT EXISTS gem_tenders (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    title TEXT,
    reference_number TEXT,
    organization TEXT,
    location TEXT,
    deadline TEXT,
    estimated_value TEXT,
    source_url TEXT NOT NULL,
    url_hash TEXT UNIQUE NOT NULL,
    keywords_matched TEXT[] DEFAULT '{}',
    user_status TEXT DEFAULT 'active' CHECK (user_status IN ('active', 'done', 'starred')),
    scraped_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    deleted_at TIMESTAMP WITH TIME ZONE
);

-- Archive table for GeM tenders
CREATE TABLE IF NOT EXISTS archive_gem_tenders (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    original_id UUID NOT NULL,
    title TEXT,
    reference_number TEXT,
    organization TEXT,
    location TEXT,
    deadline TEXT,
    estimated_value TEXT,
    source_url TEXT,
    keywords_matched TEXT[] DEFAULT '{}',
    user_status TEXT DEFAULT 'active',
    scraped_at TIMESTAMP WITH TIME ZONE,
    archived_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    archive_reason TEXT NOT NULL CHECK (archive_reason IN ('expired', 'manual_delete', 'pipeline_cleanup'))
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_gem_tenders_deleted_at ON gem_tenders(deleted_at);
CREATE INDEX IF NOT EXISTS idx_gem_tenders_deadline ON gem_tenders(deadline);
CREATE INDEX IF NOT EXISTS idx_gem_tenders_user_status ON gem_tenders(user_status);
CREATE INDEX IF NOT EXISTS idx_gem_tenders_keywords ON gem_tenders USING GIN(keywords_matched);
CREATE INDEX IF NOT EXISTS idx_archive_gem_tenders_original ON archive_gem_tenders(original_id);
CREATE INDEX IF NOT EXISTS idx_archive_gem_tenders_archived_at ON archive_gem_tenders(archived_at);

-- Trigger to update updated_at
CREATE OR REPLACE FUNCTION update_gem_tenders_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER update_gem_tenders_updated_at
    BEFORE UPDATE ON gem_tenders
    FOR EACH ROW
    EXECUTE FUNCTION update_gem_tenders_updated_at();

-- Row Level Security (RLS)
ALTER TABLE gem_tenders ENABLE ROW LEVEL SECURITY;
ALTER TABLE archive_gem_tenders ENABLE ROW LEVEL SECURITY;

-- Policies for authenticated users
CREATE POLICY "Enable all for authenticated users" ON gem_tenders
    FOR ALL
    TO authenticated
    USING (true)
    WITH CHECK (true);

CREATE POLICY "Enable all for authenticated users" ON archive_gem_tenders
    FOR ALL
    TO authenticated
    USING (true)
    WITH CHECK (true);

-- Service role has full access by default