-- ─── Extensions ───────────────────────────────────────────────
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";

-- ─── ENUMs ────────────────────────────────────────────────────
CREATE TYPE verdict_enum AS ENUM ('ALLOW', 'WARN', 'BLOCK');
CREATE TYPE feedback_label_enum AS ENUM ('TRUE_PHISHING', 'FALSE_POSITIVE');
CREATE TYPE indicator_type_enum AS ENUM ('URL', 'DOMAIN', 'IP');
CREATE TYPE indicator_source_enum AS ENUM ('PHISHTANK', 'OPENPHISH', 'URLHAUS');
CREATE TYPE incident_status_enum AS ENUM ('ACTIVE', 'RESOLVED');
CREATE TYPE user_role_enum AS ENUM ('analyst', 'admin');

-- ─── API Keys ─────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS api_keys (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    key_hash CHAR(64) NOT NULL UNIQUE,          -- SHA-256 of the actual key
    name VARCHAR(255) NOT NULL,
    is_active BOOLEAN DEFAULT TRUE,
    rate_limit_per_min INTEGER DEFAULT 60,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    last_used_at TIMESTAMPTZ
);

-- ─── Users ────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS users (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    email VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    role user_role_enum DEFAULT 'analyst',
    is_active BOOLEAN DEFAULT TRUE,
    api_key_id UUID REFERENCES api_keys(id) ON DELETE SET NULL,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- ─── Verdicts ─────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS verdicts (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    url_hash CHAR(64) NOT NULL,                 -- SHA-256 of analysed URL
    verdict verdict_enum NOT NULL,
    final_score FLOAT NOT NULL,
    score_nlp FLOAT,
    score_url FLOAT,
    score_visual FLOAT,
    score_adversarial FLOAT,
    explainability JSONB DEFAULT '{}',
    api_key_id UUID REFERENCES api_keys(id) ON DELETE SET NULL,
    geo_country CHAR(2),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    feedback_label feedback_label_enum NULL
);

-- ─── Threat Indicators ────────────────────────────────────────
CREATE TABLE IF NOT EXISTS threat_indicators (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    indicator_type indicator_type_enum NOT NULL,
    indicator_value TEXT NOT NULL,
    source indicator_source_enum NOT NULL,
    first_seen TIMESTAMPTZ DEFAULT NOW(),
    last_seen TIMESTAMPTZ DEFAULT NOW(),
    confidence_score FLOAT,
    tags JSONB DEFAULT '[]',
    UNIQUE(indicator_type, indicator_value, source)
);

-- ─── Incidents ────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS incidents (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    campaign_name VARCHAR(255),                 -- auto-generated
    affected_brand VARCHAR(255),
    block_count INTEGER DEFAULT 0,
    first_seen TIMESTAMPTZ DEFAULT NOW(),
    last_seen TIMESTAMPTZ DEFAULT NOW(),
    status incident_status_enum DEFAULT 'ACTIVE',
    hosting_asn VARCHAR(100),
    meta JSONB DEFAULT '{}'
);

-- ─── Email Analysis ───────────────────────────────────────────
CREATE TABLE IF NOT EXISTS email_analysis (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    verdict_id UUID REFERENCES verdicts(id) ON DELETE CASCADE,
    from_hash CHAR(64),                         -- SHA-256 of sender address
    reply_to_hash CHAR(64),
    subject_text TEXT,
    body_text TEXT,
    links JSONB DEFAULT '[]',
    headers JSONB DEFAULT '{}',
    spf_pass BOOLEAN,
    dkim_pass BOOLEAN,
    dmarc_pass BOOLEAN,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- ─── Screenshots ──────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS screenshots (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    verdict_id UUID REFERENCES verdicts(id) ON DELETE CASCADE,
    minio_object_key VARCHAR(512) NOT NULL,
    brand_detected VARCHAR(255),
    brand_similarity_score FLOAT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- ─── Feedback ─────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS feedback (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    verdict_id UUID NOT NULL REFERENCES verdicts(id) ON DELETE CASCADE,
    user_id UUID REFERENCES users(id) ON DELETE SET NULL,
    label feedback_label_enum NOT NULL,
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
    metrics JSONB DEFAULT '{}',                 -- precision, recall, f1, auc, brier
    is_active BOOLEAN DEFAULT FALSE,
    trained_at TIMESTAMPTZ DEFAULT NOW(),
    deployed_at TIMESTAMPTZ,
    mlflow_run_id VARCHAR(255),
    UNIQUE(model_name, version)
);

-- ─── Retraining Jobs ──────────────────────────────────────────
CREATE TABLE IF NOT EXISTS retraining_jobs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    model_name VARCHAR(100) NOT NULL,
    status VARCHAR(50) DEFAULT 'PENDING',       -- PENDING | RUNNING | PROMOTED | QUARANTINED
    samples_used INTEGER,
    metrics JSONB DEFAULT '{}',
    mlflow_run_id VARCHAR(255),
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW()
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
CREATE INDEX IF NOT EXISTS idx_verdicts_url_hash ON verdicts(url_hash);
CREATE INDEX IF NOT EXISTS idx_verdicts_created_at ON verdicts(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_verdicts_verdict ON verdicts(verdict);
CREATE INDEX IF NOT EXISTS idx_verdicts_api_key_id ON verdicts(api_key_id);
CREATE INDEX IF NOT EXISTS idx_threat_indicators_value ON threat_indicators(indicator_type, indicator_value);
CREATE INDEX IF NOT EXISTS idx_threat_indicators_source ON threat_indicators(source);
CREATE INDEX IF NOT EXISTS idx_incidents_status ON incidents(status);
CREATE INDEX IF NOT EXISTS idx_incidents_brand ON incidents(affected_brand);
CREATE INDEX IF NOT EXISTS idx_feedback_verdict_id ON feedback(verdict_id);
CREATE INDEX IF NOT EXISTS idx_email_analysis_verdict_id ON email_analysis(verdict_id);
CREATE INDEX IF NOT EXISTS idx_audit_log_created_at ON audit_log(created_at DESC);

-- ─── Default Admin API Key ────────────────────────────────────
-- Key value: apds-dev-key-changeme (SHA-256 hash stored)
INSERT INTO api_keys (key_hash, name, rate_limit_per_min)
VALUES (
    'a665a45920422f9d417e4867efdc4fb8a04a1f3fff1fa07e998e86f7f7a27ae3',
    'default-dev-key',
    1000
) ON CONFLICT (key_hash) DO NOTHING;

-- ─── Default Admin User ───────────────────────────────────────
-- Password: admin123 (bcrypt) — change immediately after first login
INSERT INTO users (email, password_hash, role)
VALUES (
    'admin@apds.local',
    '$2b$12$EixZaYVK1fsbw1ZfbX3OXePaWxn96p36WQoeG6Lruj3vjPGga31lW',
    'admin'
) ON CONFLICT (email) DO NOTHING;