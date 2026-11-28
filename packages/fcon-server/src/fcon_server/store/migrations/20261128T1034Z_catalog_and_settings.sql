-- The catalog and the operator's settings (catalog-and-settings, design § How
-- it is built). Expand-only: four new tables. The rules on names and values
-- live in fcon_server.catalog; the checks here only keep a bug from storing
-- what those rules refuse.

-- Rows only added: one recorded version of one package, never changed
-- (decision 2). checksum is the SHA-256 of its definitions, spelled canonically.
CREATE TABLE fcon.package_version (
    tenant_id text COLLATE pg_c_utf8 NOT NULL REFERENCES fcon.tenant (tenant_id),
    id uuid NOT NULL,
    package text COLLATE pg_c_utf8 NOT NULL
        CONSTRAINT package_version_package_rule CHECK (package ~ '^[a-z][a-z0-9-]{0,63}$'),
    version text COLLATE pg_c_utf8 NOT NULL
        CONSTRAINT package_version_version_rule CHECK (char_length(version) BETWEEN 1 AND 64),
    checksum text COLLATE pg_c_utf8 NOT NULL,
    created_at timestamptz NOT NULL,
    created_by text NOT NULL,
    PRIMARY KEY (tenant_id, id),
    CONSTRAINT package_version_unique UNIQUE (tenant_id, package, version)
);

-- Rows change: the stable identity of one flow, dataset or route (decision 1).
-- A rename changes name in place; package_version_id is the latest recorded
-- version of its package that declares it; is_in_code says whether the latest
-- recorded version of its package still does (decision 7).
CREATE TABLE fcon.catalog_entry (
    tenant_id text COLLATE pg_c_utf8 NOT NULL REFERENCES fcon.tenant (tenant_id),
    id uuid NOT NULL,
    kind text NOT NULL CONSTRAINT catalog_entry_kind CHECK (kind IN ('flow', 'dataset', 'route')),
    name text COLLATE pg_c_utf8 NOT NULL,
    package text COLLATE pg_c_utf8 NOT NULL,
    package_version_id uuid NOT NULL,
    is_in_code boolean NOT NULL,
    created_at timestamptz NOT NULL,
    created_by text NOT NULL,
    updated_at timestamptz NOT NULL,
    updated_by text NOT NULL,
    row_version bigint NOT NULL,
    PRIMARY KEY (tenant_id, id),
    CONSTRAINT catalog_entry_name_unique UNIQUE (tenant_id, name),
    CONSTRAINT catalog_entry_of_package_version FOREIGN KEY (tenant_id, package_version_id)
        REFERENCES fcon.package_version (tenant_id, id)
);

CREATE INDEX catalog_entry_package_version_id ON fcon.catalog_entry (tenant_id, package_version_id);
CREATE INDEX catalog_entry_package ON fcon.catalog_entry (tenant_id, package);

-- Rows only added: one package version's own copy of one entry's definition
-- (decision 2), as that version spelled its name, the code's whole item.
CREATE TABLE fcon.catalog_definition (
    tenant_id text COLLATE pg_c_utf8 NOT NULL REFERENCES fcon.tenant (tenant_id),
    id uuid NOT NULL,
    package_version_id uuid NOT NULL,
    entry_id uuid NOT NULL,
    name text COLLATE pg_c_utf8 NOT NULL,
    renamed_from text COLLATE pg_c_utf8,
    definition jsonb NOT NULL,
    created_at timestamptz NOT NULL,
    created_by text NOT NULL,
    PRIMARY KEY (tenant_id, id),
    CONSTRAINT catalog_definition_unique UNIQUE (tenant_id, package_version_id, entry_id),
    CONSTRAINT catalog_definition_of_package_version FOREIGN KEY (tenant_id, package_version_id)
        REFERENCES fcon.package_version (tenant_id, id),
    CONSTRAINT catalog_definition_of_entry FOREIGN KEY (tenant_id, entry_id)
        REFERENCES fcon.catalog_entry (tenant_id, id)
);

CREATE INDEX catalog_definition_entry_id ON fcon.catalog_definition (tenant_id, entry_id);

-- Rows change: an operator's value for one setting of one entry, in the
-- setting's canonical spelling; null once cleared, never deleted (decision 6).
CREATE TABLE fcon.operator_setting (
    tenant_id text COLLATE pg_c_utf8 NOT NULL REFERENCES fcon.tenant (tenant_id),
    id uuid NOT NULL,
    entry_id uuid NOT NULL,
    setting text COLLATE pg_c_utf8 NOT NULL,
    value text,
    created_at timestamptz NOT NULL,
    created_by text NOT NULL,
    updated_at timestamptz NOT NULL,
    updated_by text NOT NULL,
    row_version bigint NOT NULL,
    PRIMARY KEY (tenant_id, id),
    CONSTRAINT operator_setting_unique UNIQUE (tenant_id, entry_id, setting),
    CONSTRAINT operator_setting_of_entry FOREIGN KEY (tenant_id, entry_id)
        REFERENCES fcon.catalog_entry (tenant_id, id)
);
