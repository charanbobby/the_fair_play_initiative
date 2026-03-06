-- ============================================================
-- Fair Play Initiative — PostgreSQL Schema
-- Target: Supabase (PostgreSQL)
-- Run order matters: each table only references tables above it.
-- Table names match SQLAlchemy ORM __tablename__ values.
-- ============================================================

-- ============================================================
-- 1. Region
-- ============================================================
CREATE TABLE IF NOT EXISTS regions (
    id          TEXT PRIMARY KEY,          -- slug e.g. 'us-west'
    name        TEXT        NOT NULL,
    code        TEXT        NOT NULL,      -- e.g. 'US-W'
    timezone    TEXT        NOT NULL,      -- IANA e.g. 'America/Los_Angeles'
    labor_laws  TEXT
);

-- ============================================================
-- 2. Organization
-- ============================================================
CREATE TABLE IF NOT EXISTS organizations (
    id      TEXT    PRIMARY KEY,           -- slug e.g. 'org-1'
    name    TEXT    NOT NULL,
    code    TEXT    NOT NULL,
    active  BOOLEAN NOT NULL DEFAULT TRUE
);

-- ============================================================
-- 3. OrganizationRegion  (M2M join — no extra columns)
-- ============================================================
CREATE TABLE IF NOT EXISTS organization_region (
    organization_id TEXT NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    region_id       TEXT NOT NULL REFERENCES regions(id)       ON DELETE CASCADE,
    PRIMARY KEY (organization_id, region_id)
);

-- ============================================================
-- 4. Policy
-- ============================================================
CREATE TABLE IF NOT EXISTS policies (
    id              TEXT    PRIMARY KEY,
    name            TEXT    NOT NULL,
    organization_id TEXT    NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    region_id       TEXT    NOT NULL REFERENCES regions(id)       ON DELETE CASCADE,
    active          BOOLEAN NOT NULL DEFAULT TRUE,
    effective_date  DATE
);

-- ============================================================
-- 5. Rule
-- ============================================================
CREATE TABLE IF NOT EXISTS rules (
    id          SERIAL  PRIMARY KEY,
    policy_id   TEXT    REFERENCES policies(id) ON DELETE CASCADE,  -- NULL = global rule
    name        TEXT    NOT NULL,
    condition   TEXT    NOT NULL,    -- 'late' | 'early' | 'absence' | 'no-call'
    threshold   INTEGER NOT NULL DEFAULT 0,  -- minutes; 0 = any deviation
    points      REAL    NOT NULL DEFAULT 0,
    description TEXT,
    active      BOOLEAN NOT NULL DEFAULT TRUE
);

-- ============================================================
-- 6. Employee
-- ============================================================
CREATE TABLE IF NOT EXISTS employees (
    id              SERIAL  PRIMARY KEY,
    first_name      TEXT    NOT NULL,
    last_name       TEXT    NOT NULL,
    email           TEXT    NOT NULL UNIQUE,
    department      TEXT,
    position        TEXT,
    start_date      DATE,
    points          REAL    NOT NULL DEFAULT 0,
    trend           TEXT    NOT NULL DEFAULT 'stable',  -- 'up' | 'down' | 'stable'
    next_reset      DATE,
    organization_id TEXT    NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    region_id       TEXT    NOT NULL REFERENCES regions(id)       ON DELETE CASCADE,
    policy_id       TEXT             REFERENCES policies(id)       ON DELETE SET NULL
);

-- ============================================================
-- 7. PointHistory  (immutable ledger)
-- ============================================================
CREATE TABLE IF NOT EXISTS point_history (
    id          SERIAL  PRIMARY KEY,
    employee_id INTEGER NOT NULL REFERENCES employees(id) ON DELETE CASCADE,
    date        DATE    NOT NULL,
    type        TEXT    NOT NULL,   -- violation name OR 'Manual Override: excuse' etc.
    points      REAL    NOT NULL,   -- positive = penalty; negative = deduction
    status      TEXT    NOT NULL DEFAULT 'Active',  -- 'Active' | 'Excused' | 'Approved'
    reason      TEXT                                -- filled for manual overrides
);

-- ============================================================
-- 8. AttendanceLog
-- ============================================================
CREATE TABLE IF NOT EXISTS attendance_logs (
    id              SERIAL  PRIMARY KEY,
    employee_id     INTEGER NOT NULL REFERENCES employees(id)       ON DELETE CASCADE,
    organization_id TEXT    NOT NULL REFERENCES organizations(id)   ON DELETE CASCADE,
    region_id       TEXT    NOT NULL REFERENCES regions(id)         ON DELETE CASCADE,
    policy_id       TEXT             REFERENCES policies(id)        ON DELETE SET NULL,
    date            DATE    NOT NULL,
    scheduled_in    TEXT,            -- '09:00 AM' format
    scheduled_out   TEXT,
    actual_in       TEXT,            -- empty string = absent / not recorded
    actual_out      TEXT,
    violation       TEXT,            -- rule name if violated; NULL if compliant
    points          REAL    NOT NULL DEFAULT 0,
    status          TEXT    NOT NULL DEFAULT 'Compliant'  -- 'Compliant' | 'Violation' | 'Active'
);

-- ============================================================
-- 9. Alert
-- ============================================================
CREATE TABLE IF NOT EXISTS alerts (
    id              SERIAL       PRIMARY KEY,
    organization_id TEXT         REFERENCES organizations(id) ON DELETE CASCADE,  -- NULL = platform-wide
    type            TEXT         NOT NULL,   -- 'info' | 'warning' | 'danger' | 'success'
    message         TEXT         NOT NULL,
    created_at      TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

-- ============================================================
-- 10. AnalysisLog — auto-saved on each policy analysis run
-- ============================================================
CREATE TABLE IF NOT EXISTS analysis_logs (
    id              SERIAL       PRIMARY KEY,
    filename        TEXT         NOT NULL,
    step            TEXT         NOT NULL,      -- 'extract' | 'plan'
    llm_model       TEXT         NOT NULL,
    prompt_tokens   INTEGER      NOT NULL DEFAULT 0,
    completion_tokens INTEGER    NOT NULL DEFAULT 0,
    total_tokens    INTEGER      NOT NULL DEFAULT 0,
    duration_ms     INTEGER      NOT NULL DEFAULT 0,
    created_at      TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

-- ============================================================
-- 11. AnalysisFeedback — user-submitted Good/Partial/Bad ratings
-- ============================================================
CREATE TABLE IF NOT EXISTS analysis_feedback (
    id              SERIAL       PRIMARY KEY,
    step            TEXT         NOT NULL,      -- 'extract' | 'plan'
    rating          TEXT         NOT NULL,      -- 'good' | 'partial' | 'bad'
    llm_model       TEXT         NOT NULL,
    filename        TEXT,
    created_at      TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

-- ============================================================
-- Indexes
-- ============================================================
CREATE INDEX IF NOT EXISTS idx_employee_org       ON employees(organization_id);
CREATE INDEX IF NOT EXISTS idx_employee_region    ON employees(region_id);
CREATE INDEX IF NOT EXISTS idx_rule_policy        ON rules(policy_id);
CREATE INDEX IF NOT EXISTS idx_point_history_emp  ON point_history(employee_id);
CREATE INDEX IF NOT EXISTS idx_attendance_emp     ON attendance_logs(employee_id);
CREATE INDEX IF NOT EXISTS idx_attendance_org     ON attendance_logs(organization_id);
CREATE INDEX IF NOT EXISTS idx_alert_org          ON alerts(organization_id);
