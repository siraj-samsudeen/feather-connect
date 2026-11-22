-- The first tables (design point 11): the schema fcon, the record of the
-- upgrades, the tenants with the default one, and the audit log. Times come
-- from the runner's clock (fcon.now): SQL never calls now().

CREATE SCHEMA fcon;

-- Rows only added: the runner records each upgrade it applied.
CREATE TABLE fcon.migration (
    name text COLLATE pg_c_utf8 PRIMARY KEY,
    checksum text NOT NULL,
    created_at timestamptz NOT NULL,
    created_by text NOT NULL
);

-- Rows change: kind and made_from let sandboxes come in M2 (design point 1).
CREATE TABLE fcon.tenant (
    tenant_id text COLLATE pg_c_utf8 PRIMARY KEY
        CONSTRAINT tenant_id_rule CHECK (tenant_id ~ '^[a-z][a-z0-9-]{0,39}$'),
    kind text NOT NULL CONSTRAINT tenant_kind CHECK (kind IN ('production', 'sandbox')),
    made_from text COLLATE pg_c_utf8 REFERENCES fcon.tenant (tenant_id),
    created_at timestamptz NOT NULL,
    created_by text NOT NULL,
    updated_at timestamptz NOT NULL,
    updated_by text NOT NULL,
    row_version bigint NOT NULL
);

INSERT INTO fcon.tenant (tenant_id, kind, created_at, created_by, updated_at, updated_by, row_version)
VALUES (
    'default',
    'production',
    current_setting('fcon.now')::timestamptz,
    'system:migration',
    current_setting('fcon.now')::timestamptz,
    'system:migration',
    1
);

-- Rows only added, one month per partition (design point 16); fcon db
-- upgrade makes the months ahead. No default partition (decision 4).
CREATE TABLE fcon.audit (
    tenant_id text COLLATE pg_c_utf8 NOT NULL REFERENCES fcon.tenant (tenant_id),
    id uuid NOT NULL,
    created_at timestamptz NOT NULL,
    created_by text NOT NULL,
    request_id text COLLATE pg_c_utf8 NOT NULL,
    table_name text COLLATE pg_c_utf8 NOT NULL,
    action text NOT NULL CONSTRAINT audit_action CHECK (action IN ('insert', 'update', 'delete', 'refused')),
    row_key text COLLATE pg_c_utf8 NOT NULL,
    before jsonb,
    after jsonb,
    reason text,
    PRIMARY KEY (tenant_id, id, created_at)
) PARTITION BY RANGE (created_at);

CREATE INDEX audit_row ON fcon.audit (tenant_id, table_name, row_key);

-- The log is never changed, whoever asks (design point 16).
CREATE FUNCTION fcon.audit_refuse_change() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    RAISE EXCEPTION 'fcon.audit records are never changed or deleted'
        USING ERRCODE = 'insufficient_privilege';
END;
$$;

CREATE TRIGGER audit_refuse_change BEFORE UPDATE OR DELETE ON fcon.audit
    FOR EACH ROW EXECUTE FUNCTION fcon.audit_refuse_change();
