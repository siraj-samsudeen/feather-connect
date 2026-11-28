-- The stored data (stored-versions, design § Tables): partitions, versions,
-- their record blocks, record state, each dataset's progress and the
-- current-state snapshot. Expand-only: eight new tables.
--
-- dataset_id and package_version_id are plain ids for now: the catalog's
-- tables (fcon.catalog_entry, fcon.package_version) come from another change,
-- and their foreign keys are added by a later migration once both are in.
-- The column "values" is quoted: VALUES is an SQL keyword.

-- Rows change: a dataset's slice, by its values spelled once canonically
-- (JSON, keys sorted, no spaces; design decision 10).
CREATE TABLE fcon.partition (
    tenant_id text COLLATE pg_c_utf8 NOT NULL REFERENCES fcon.tenant (tenant_id),
    id uuid NOT NULL,
    dataset_id uuid NOT NULL,
    "values" jsonb NOT NULL,
    values_key text COLLATE pg_c_utf8 NOT NULL,
    starts_at timestamptz,
    ends_at timestamptz,
    labels jsonb NOT NULL DEFAULT '{}',
    last_version_number bigint NOT NULL DEFAULT 0,
    position jsonb,
    created_at timestamptz NOT NULL,
    created_by text NOT NULL,
    updated_at timestamptz NOT NULL,
    updated_by text NOT NULL,
    row_version bigint NOT NULL,
    PRIMARY KEY (tenant_id, id),
    CONSTRAINT partition_values_unique UNIQUE (tenant_id, dataset_id, values_key)
);

-- Rows change: one read of a slice, open while it reads (its read lock,
-- decision 5), then sealed with its number and commit number, or cleaned up.
CREATE TABLE fcon.version (
    tenant_id text COLLATE pg_c_utf8 NOT NULL REFERENCES fcon.tenant (tenant_id),
    id uuid NOT NULL,
    dataset_id uuid NOT NULL,
    partition_id uuid NOT NULL,
    read_id uuid NOT NULL,
    number bigint,
    commit_number bigint,
    kind text NOT NULL CONSTRAINT version_kind CHECK (kind IN ('complete', 'changes_only', 'starting')),
    state text NOT NULL
        CONSTRAINT version_state CHECK (state IN ('open', 'sealed', 'cleaned_up', 'lost', 'expired')),
    records_read bigint NOT NULL DEFAULT 0,
    added bigint NOT NULL DEFAULT 0,
    changed bigint NOT NULL DEFAULT 0,
    deleted bigint NOT NULL DEFAULT 0,
    unchanged bigint NOT NULL DEFAULT 0,
    package_version_id uuid,
    shape jsonb,
    read_cursor jsonb,
    position jsonb,
    lease_expires_at timestamptz,
    read_started_at timestamptz NOT NULL,
    sealed_at timestamptz,
    moved_from_partition_ids uuid[] NOT NULL DEFAULT '{}',
    block_count integer NOT NULL DEFAULT 0,
    created_at timestamptz NOT NULL,
    created_by text NOT NULL,
    updated_at timestamptz NOT NULL,
    updated_by text NOT NULL,
    row_version bigint NOT NULL,
    PRIMARY KEY (tenant_id, id),
    CONSTRAINT version_of_partition FOREIGN KEY (tenant_id, partition_id) REFERENCES fcon.partition (tenant_id, id),
    CONSTRAINT version_sealed_numbered CHECK (
        state IN ('open', 'cleaned_up') OR (number IS NOT NULL AND commit_number IS NOT NULL)
    ),
    -- Also the index on the partition: an open version's number is null, and nulls never clash.
    CONSTRAINT version_number_unique UNIQUE (tenant_id, partition_id, number)
);

-- One open read per slice: a second is refused at once (decision 5).
CREATE UNIQUE INDEX version_one_open ON fcon.version (tenant_id, partition_id) WHERE state = 'open';
CREATE INDEX version_commit ON fcon.version (tenant_id, dataset_id, commit_number);
CREATE INDEX version_read ON fcon.version (tenant_id, read_id);

-- Rows only added, written in bulk (ADR 0022): a version's records as one
-- zstd Parquet file each, one day per partition (decision 4, ADR 0023); the
-- upgrade makes the days ahead. No default partition.
CREATE TABLE fcon.record_block (
    tenant_id text COLLATE pg_c_utf8 NOT NULL REFERENCES fcon.tenant (tenant_id),
    id uuid NOT NULL,
    created_at timestamptz NOT NULL,
    created_by text NOT NULL,
    version_id uuid NOT NULL,
    number integer NOT NULL,
    kind text NOT NULL CONSTRAINT record_block_kind CHECK (kind IN ('records', 'keys')),
    row_count integer NOT NULL,
    left_out_rows integer[] NOT NULL DEFAULT '{}',
    location text NOT NULL DEFAULT 'database' CONSTRAINT record_block_location CHECK (location IN ('database')),
    data bytea,
    PRIMARY KEY (tenant_id, id, created_at),
    CONSTRAINT record_block_of_version FOREIGN KEY (tenant_id, version_id) REFERENCES fcon.version (tenant_id, id),
    CONSTRAINT record_block_data_here CHECK (location <> 'database' OR data IS NOT NULL)
) PARTITION BY RANGE (created_at);

CREATE INDEX record_block_version ON fcon.record_block (tenant_id, version_id, kind, number);

-- Rows change, written in bulk (ADR 0022): each record's fingerprint, slice
-- and last change. Half of each page is kept free so a seal's update is HOT
-- (decision 2). changed_version_id has no index and no foreign key, an
-- exception to convention 14: it changes on every update, and an index on
-- it would make no update HOT. Nothing looks records up by it.
CREATE TABLE fcon.record_state (
    tenant_id text COLLATE pg_c_utf8 NOT NULL REFERENCES fcon.tenant (tenant_id),
    id uuid NOT NULL,
    dataset_id uuid NOT NULL,
    key text COLLATE pg_c_utf8 NOT NULL,
    partition_id uuid NOT NULL,
    fingerprint bytea NOT NULL CONSTRAINT record_state_fingerprint CHECK (octet_length(fingerprint) = 32),
    changed_version_id uuid NOT NULL,
    is_present boolean NOT NULL,
    created_at timestamptz NOT NULL,
    created_by text NOT NULL,
    updated_at timestamptz NOT NULL,
    updated_by text NOT NULL,
    row_version bigint NOT NULL,
    PRIMARY KEY (tenant_id, id),
    CONSTRAINT record_state_key_unique UNIQUE (tenant_id, dataset_id, key),
    CONSTRAINT record_state_of_partition FOREIGN KEY (tenant_id, partition_id) REFERENCES fcon.partition (tenant_id, id)
) WITH (fillfactor = 50);

CREATE INDEX record_state_partition ON fcon.record_state (tenant_id, partition_id);

-- Rows change: a dataset's last commit number and its position, moved only
-- inside a seal.
CREATE TABLE fcon.dataset_progress (
    tenant_id text COLLATE pg_c_utf8 NOT NULL REFERENCES fcon.tenant (tenant_id),
    dataset_id uuid NOT NULL,
    last_commit_number bigint NOT NULL DEFAULT 0,
    position jsonb,
    created_at timestamptz NOT NULL,
    created_by text NOT NULL,
    updated_at timestamptz NOT NULL,
    updated_by text NOT NULL,
    row_version bigint NOT NULL,
    PRIMARY KEY (tenant_id, dataset_id)
);

-- Rows change: a slice's snapshot base as of a commit number (decision 9);
-- one current base per slice.
CREATE TABLE fcon.snapshot_base (
    tenant_id text COLLATE pg_c_utf8 NOT NULL REFERENCES fcon.tenant (tenant_id),
    id uuid NOT NULL,
    dataset_id uuid NOT NULL,
    partition_id uuid NOT NULL,
    commit_number bigint NOT NULL,
    state text NOT NULL CONSTRAINT snapshot_base_state CHECK (state IN ('building', 'current', 'replaced')),
    block_count integer NOT NULL DEFAULT 0,
    created_at timestamptz NOT NULL,
    created_by text NOT NULL,
    updated_at timestamptz NOT NULL,
    updated_by text NOT NULL,
    row_version bigint NOT NULL,
    PRIMARY KEY (tenant_id, id),
    CONSTRAINT snapshot_base_of_partition FOREIGN KEY (tenant_id, partition_id)
        REFERENCES fcon.partition (tenant_id, id)
);

CREATE UNIQUE INDEX snapshot_base_one_current ON fcon.snapshot_base (tenant_id, partition_id) WHERE state = 'current';
CREATE INDEX snapshot_base_partition ON fcon.snapshot_base (tenant_id, partition_id, commit_number);

-- Rows only added, written in bulk (ADR 0022): a base's content, kept while
-- the dataset exists, so not split by day.
CREATE TABLE fcon.snapshot_block (
    tenant_id text COLLATE pg_c_utf8 NOT NULL REFERENCES fcon.tenant (tenant_id),
    id uuid NOT NULL,
    base_id uuid NOT NULL,
    number integer NOT NULL,
    row_count integer NOT NULL,
    location text NOT NULL DEFAULT 'database' CONSTRAINT snapshot_block_location CHECK (location IN ('database')),
    data bytea,
    created_at timestamptz NOT NULL,
    created_by text NOT NULL,
    PRIMARY KEY (tenant_id, id),
    CONSTRAINT snapshot_block_of_base FOREIGN KEY (tenant_id, base_id) REFERENCES fcon.snapshot_base (tenant_id, id),
    CONSTRAINT snapshot_block_data_here CHECK (location <> 'database' OR data IS NOT NULL)
);

CREATE INDEX snapshot_block_base ON fcon.snapshot_block (tenant_id, base_id, number);

-- Rows only added: a commit number someone needs kept, and why.
CREATE TABLE fcon.snapshot_pin (
    tenant_id text COLLATE pg_c_utf8 NOT NULL REFERENCES fcon.tenant (tenant_id),
    id uuid NOT NULL,
    dataset_id uuid NOT NULL,
    commit_number bigint NOT NULL,
    reason text NOT NULL,
    created_at timestamptz NOT NULL,
    created_by text NOT NULL,
    PRIMARY KEY (tenant_id, id)
);

CREATE INDEX snapshot_pin_commit ON fcon.snapshot_pin (tenant_id, dataset_id, commit_number);
