-- ─── Extensions ───────────────────────────────────────────────
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";

-- ─── Users ────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS users (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    email VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    role VARCHAR(50) DEFAULT 'analyst',         -- analyst | admin
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- ─── Scan Results ─────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS scan_results (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    input_type VARCHAR(50) NOT NULL,            -- email | url | page
    raw_input TEXT,
    final_verdict VARCHAR(50) NOT NULL,         -- phishing | legitimate | suspicious
    confidence_score FLOAT NOT NULL,
    risk_level VARCHAR(20) NOT NULL,            -- critical | high | medium | low
    processing_time_ms INTEGER,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    user_id UUID REFERENCES users(id) ON DELETE SET NULL
);

-- ─── Per-Model Scores ─────────────────────────────────────────
CREATE TABLE IF NOT EXISTS model_scores (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    scan_id UUID NOT NULL REFERENCES scan_results(id) ON DELETE CASCADE,
    model_name VARCHAR(100) NOT NULL,           -- nlp | url_gnn | visual | adversarial
    score FLOAT NOT NULL,
    confidence FLOAT NOT NULL,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- ─── URL Intelligence ─────────────────────────────────────────
CREATE TABLE IF NOT EXISTS url_intel (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    url TEXT NOT NULL,
    url_hash VARCHAR(64) UNIQUE NOT NULL,       -- SHA256 for dedup
    domain VARCHAR(255),
    is_malicious BOOLEAN,
    virustotal_score FLOAT,
    urlscan_score FLOAT,
    redirect_chain JSONB DEFAULT '[]',
    whois_data JSONB DEFAULT '{}',
    dns_records JSONB DEFAULT '{}',
    first_seen TIMESTAMPTZ DEFAULT NOW(),
    last_checked TIMESTAMPTZ DEFAULT NOW()
);

-- ─── Email Analysis ───────────────────────────────────────────
CREATE TABLE IF NOT EXISTS email_analysis (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    scan_id UUID NOT NULL REFERENCES scan_results(id) ON DELETE CASCADE,
    sender_domain VARCHAR(255),
    spf_pass BOOLEAN,
    dkim_pass BOOLEAN,
    dmarc_pass BOOLEAN,
    subject_text TEXT,
    body_text TEXT,
    url_count INTEGER DEFAULT 0,
    attachment_count INTEGER DEFAULT 0,
    header_anomalies JSONB DEFAULT '[]',
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- ─── Screenshots ──────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS screenshots (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    scan_id UUID NOT NULL REFERENCES scan_results(id) ON DELETE CASCADE,
    minio_object_key VARCHAR(512) NOT NULL,
    brand_detected VARCHAR(255),
    brand_similarity_score FLOAT,
    visual_anomalies JSONB DEFAULT '[]',
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- ─── Threat Intel Cache ───────────────────────────────────────
CREATE TABLE IF NOT EXISTS threat_intel_cache (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    indicator_type VARCHAR(50) NOT NULL,        -- ip | domain | url | hash
    indicator_value TEXT NOT NULL,
    source VARCHAR(100) NOT NULL,               -- virustotal | urlscan | abuseipdb
    raw_response JSONB NOT NULL,
    is_malicious BOOLEAN,
    expires_at TIMESTAMPTZ NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(indicator_type, indicator_value, source)
);

-- ─── Feedback ─────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS feedback (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    scan_id UUID NOT NULL REFERENCES scan_results(id) ON DELETE CASCADE,
    user_id UUID REFERENCES users(id) ON DELETE SET NULL,
    correct_label VARCHAR(50) NOT NULL,         -- phishing | legitimate
    comment TEXT,
    used_for_training BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- ─── Model Registry ───────────────────────────────────────────
CREATE TABLE IF NOT EXISTS model_registry (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    model_name VARCHAR(100) NOT NULL,
    version VARCHAR(50) NOT NULL,
    minio_object_key VARCHAR(512) NOT NULL,
    metrics JSONB DEFAULT '{}',                 -- precision, recall, f1, auc
    is_active BOOLEAN DEFAULT FALSE,
    trained_at TIMESTAMPTZ DEFAULT NOW(),
    deployed_at TIMESTAMPTZ,
    UNIQUE(model_name, version)
);

-- ─── Audit Log ────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS audit_log (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID REFERENCES users(id) ON DELETE SET NULL,
    action VARCHAR(100) NOT NULL,
    resource_type VARCHAR(100),
    resource_id UUID,
    ip_address INET,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- ─── Indexes ──────────────────────────────────────────────────
CREATE INDEX IF NOT EXISTS idx_scan_results_created_at ON scan_results(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_scan_results_verdict ON scan_results(final_verdict);
CREATE INDEX IF NOT EXISTS idx_scan_results_user_id ON scan_results(user_id);
CREATE INDEX IF NOT EXISTS idx_url_intel_url_hash ON url_intel(url_hash);
CREATE INDEX IF NOT EXISTS idx_url_intel_domain ON url_intel(domain);
CREATE INDEX IF NOT EXISTS idx_threat_intel_indicator ON threat_intel_cache(indicator_type, indicator_value);
CREATE INDEX IF NOT EXISTS idx_feedback_scan_id ON feedback(scan_id);
CREATE INDEX IF NOT EXISTS idx_model_scores_scan_id ON model_scores(scan_id);
CREATE INDEX IF NOT EXISTS idx_audit_log_user_id ON audit_log(user_id);
CREATE INDEX IF NOT EXISTS idx_audit_log_created_at ON audit_log(created_at DESC);

-- ─── Default Admin User ───────────────────────────────────────
-- Password: admin123 (bcrypt hash) — change immediately after first login
INSERT INTO users (email, password_hash, role)
VALUES (
    'admin@apds.local',
    '$2b$12$EixZaYVK1fsbw1ZfbX3OXePaWxn96p36WQoeG6Lruj3vjPGga31lW',
    'admin'
) ON CONFLICT (email) DO NOTHING;