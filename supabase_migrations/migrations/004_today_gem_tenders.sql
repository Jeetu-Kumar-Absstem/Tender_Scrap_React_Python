-- supabase_migrations/migrations/004_today_gem_tenders.sql

-- Table for GeM tenders scraped today only
CREATE TABLE IF NOT EXISTS today_gem_tenders (
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

-- Indexes
CREATE INDEX IF NOT EXISTS idx_today_gem_tenders_deleted_at ON today_gem_tenders(deleted_at);
CREATE INDEX IF NOT EXISTS idx_today_gem_tenders_deadline ON today_gem_tenders(deadline);
CREATE INDEX IF NOT EXISTS idx_today_gem_tenders_user_status ON today_gem_tenders(user_status);
CREATE INDEX IF NOT EXISTS idx_today_gem_tenders_keywords ON today_gem_tenders USING GIN(keywords_matched);

-- Trigger to update updated_at
CREATE OR REPLACE FUNCTION update_today_gem_tenders_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER update_today_gem_tenders_updated_at
    BEFORE UPDATE ON today_gem_tenders
    FOR EACH ROW
    EXECUTE FUNCTION update_today_gem_tenders_updated_at();

-- Row Level Security
ALTER TABLE today_gem_tenders ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Enable all for authenticated users" ON today_gem_tenders
    FOR ALL
    TO authenticated
    USING (true)
    WITH CHECK (true);

-- Service role has full access by default
