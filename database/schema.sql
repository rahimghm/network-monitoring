-- Base de données de monitoring réseau

-- ========== Auth & RBAC (Feature 5) ==========
CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    username VARCHAR(50) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    role VARCHAR(20) NOT NULL CHECK (role IN ('admin', 'technician', 'supervisor')),
    created_at TIMESTAMP DEFAULT now()
);

-- ========== Équipements & diagnostics (existant) ==========
CREATE TABLE IF NOT EXISTS equipments (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    hostname VARCHAR(150) NOT NULL UNIQUE,
    community VARCHAR(50) DEFAULT 'public',
    last_ip VARCHAR(45),
    is_up BOOLEAN DEFAULT NULL,
    created_at TIMESTAMP DEFAULT now()
);

CREATE TABLE IF NOT EXISTS diagnostics (
    id SERIAL PRIMARY KEY,
    equipment_id INTEGER REFERENCES equipments(id) ON DELETE CASCADE,
    resolved_ip VARCHAR(45),
    is_up BOOLEAN,
    sys_descr TEXT,
    sys_uptime BIGINT,
    cpu_usage DOUBLE PRECISION,
    ram_total_kb BIGINT,
    ram_used_kb BIGINT,
    temperature_c DOUBLE PRECISION,
    error_message TEXT,
    collected_at TIMESTAMP DEFAULT now()
);

CREATE TABLE IF NOT EXISTS interface_metrics (
    id SERIAL PRIMARY KEY,
    diagnostic_id INTEGER REFERENCES diagnostics(id) ON DELETE CASCADE,
    if_index INTEGER,
    if_descr VARCHAR(150),
    oper_status VARCHAR(20),
    admin_status VARCHAR(20),
    speed_bps BIGINT,
    in_octets BIGINT,
    out_octets BIGINT,
    in_packets BIGINT,
    out_packets BIGINT,
    in_errors BIGINT,
    out_errors BIGINT,
    in_discards BIGINT,
    out_discards BIGINT,
    stp_state VARCHAR(20),
    collected_at TIMESTAMP DEFAULT now()
);

-- Migration for databases created before the extended interface metrics.
ALTER TABLE interface_metrics ADD COLUMN IF NOT EXISTS in_packets BIGINT;
ALTER TABLE interface_metrics ADD COLUMN IF NOT EXISTS out_packets BIGINT;
ALTER TABLE interface_metrics ADD COLUMN IF NOT EXISTS in_errors BIGINT;
ALTER TABLE interface_metrics ADD COLUMN IF NOT EXISTS out_errors BIGINT;
ALTER TABLE interface_metrics ADD COLUMN IF NOT EXISTS in_discards BIGINT;
ALTER TABLE interface_metrics ADD COLUMN IF NOT EXISTS out_discards BIGINT;
ALTER TABLE interface_metrics ADD COLUMN IF NOT EXISTS stp_state VARCHAR(20);

CREATE INDEX IF NOT EXISTS idx_diagnostics_equipment ON diagnostics(equipment_id);
CREATE INDEX IF NOT EXISTS idx_interface_diagnostic ON interface_metrics(diagnostic_id);

-- ========== Alertes (Feature 4) ==========
-- equipment_id NULL = seuil global (s'applique à tout équipement sans override)
CREATE TABLE IF NOT EXISTS alert_thresholds (
    id SERIAL PRIMARY KEY,
    equipment_id INTEGER REFERENCES equipments(id) ON DELETE CASCADE,
    metric VARCHAR(30) NOT NULL CHECK (metric IN ('cpu_usage', 'ram_percent', 'temperature_c')),
    operator VARCHAR(2) NOT NULL DEFAULT 'gt' CHECK (operator IN ('gt', 'lt')),
    threshold_value DOUBLE PRECISION NOT NULL,
    enabled BOOLEAN DEFAULT true,
    created_at TIMESTAMP DEFAULT now()
);

CREATE TABLE IF NOT EXISTS alert_events (
    id SERIAL PRIMARY KEY,
    equipment_id INTEGER REFERENCES equipments(id) ON DELETE CASCADE,
    diagnostic_id INTEGER REFERENCES diagnostics(id) ON DELETE CASCADE,
    metric VARCHAR(30) NOT NULL,
    value DOUBLE PRECISION,
    threshold_value DOUBLE PRECISION,
    message TEXT,
    created_at TIMESTAMP DEFAULT now()
);

-- ========== Snapshots / historique (Feature 1 + 3) ==========
CREATE TABLE IF NOT EXISTS snapshots (
    id SERIAL PRIMARY KEY,
    label VARCHAR(150) NOT NULL,
    created_by INTEGER REFERENCES users(id),
    created_at TIMESTAMP DEFAULT now()
);

-- Lie un snapshot aux diagnostics (déjà en base) capturés au moment du clic "Snapshot"
CREATE TABLE IF NOT EXISTS snapshot_items (
    id SERIAL PRIMARY KEY,
    snapshot_id INTEGER REFERENCES snapshots(id) ON DELETE CASCADE,
    equipment_id INTEGER REFERENCES equipments(id) ON DELETE CASCADE,
    diagnostic_id INTEGER REFERENCES diagnostics(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS snapshot_metrics (
    id SERIAL PRIMARY KEY,
    snapshot_id INTEGER REFERENCES snapshots(id) ON DELETE CASCADE,
    equipment_id INTEGER REFERENCES equipments(id) ON DELETE CASCADE,
    collected_at TIMESTAMP NOT NULL,
    cpu_usage DOUBLE PRECISION,
    ram_total_kb BIGINT,
    ram_used_kb BIGINT,
    is_up BOOLEAN
);

CREATE INDEX IF NOT EXISTS idx_snapshot_items_snapshot ON snapshot_items(snapshot_id);
CREATE INDEX IF NOT EXISTS idx_snapshot_metrics_snapshot ON snapshot_metrics(snapshot_id);
CREATE INDEX IF NOT EXISTS idx_alert_thresholds_equipment ON alert_thresholds(equipment_id);

-- ========== Audit logs ==========
CREATE TABLE IF NOT EXISTS audit_logs (
    id BIGSERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
    username VARCHAR(50) NOT NULL,
    role VARCHAR(20) NOT NULL,
    action VARCHAR(100) NOT NULL,
    resource VARCHAR(100),
    resource_id INTEGER,
    details JSONB,
    created_at TIMESTAMP DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_audit_logs_created_at ON audit_logs(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_audit_logs_user_id ON audit_logs(user_id);

