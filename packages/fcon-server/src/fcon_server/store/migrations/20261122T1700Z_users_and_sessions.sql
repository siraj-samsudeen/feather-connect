-- Users, their sessions and the sign-in attempts (sign-in, design § How it
-- is built). Expand-only: three new tables. The rules on names and passwords
-- live in fcon_server.users; the checks here only keep a bug from storing
-- what those rules refuse.

-- Rows change: a user is never deleted, only disabled (point 2).
CREATE TABLE fcon.user (
    tenant_id text COLLATE pg_c_utf8 NOT NULL REFERENCES fcon.tenant (tenant_id),
    id uuid NOT NULL,
    name text COLLATE pg_c_utf8 NOT NULL CONSTRAINT user_name_rule CHECK (name ~ '^[a-z0-9._@+-]{1,64}$'),
    display_name text,
    role text NOT NULL
        CONSTRAINT user_role CHECK (role IN ('viewer', 'operator', 'developer', 'administrator')),
    state text NOT NULL CONSTRAINT user_state CHECK (state IN ('active', 'disabled')),
    is_hold_approver boolean NOT NULL DEFAULT false,
    is_personal_data_reader boolean NOT NULL DEFAULT false,
    password_hash text NOT NULL,
    must_choose_password boolean NOT NULL,
    created_at timestamptz NOT NULL,
    created_by text NOT NULL,
    updated_at timestamptz NOT NULL,
    updated_by text NOT NULL,
    row_version bigint NOT NULL,
    PRIMARY KEY (tenant_id, id),
    CONSTRAINT user_name_unique UNIQUE (tenant_id, name)
);

-- Rows change: signing out sets ended_at; nothing is deleted (point 4). The
-- browser holds the id; only its SHA-256 is kept here.
CREATE TABLE fcon.session (
    tenant_id text COLLATE pg_c_utf8 NOT NULL REFERENCES fcon.tenant (tenant_id),
    id uuid NOT NULL,
    user_id uuid NOT NULL,
    id_hash text COLLATE pg_c_utf8 NOT NULL,
    form_token text COLLATE pg_c_utf8 NOT NULL,
    made_by text NOT NULL CONSTRAINT session_made_by CHECK (made_by IN ('password')),
    address text,
    user_agent text,
    last_seen_at timestamptz NOT NULL,
    expires_at timestamptz NOT NULL,
    ended_at timestamptz,
    created_at timestamptz NOT NULL,
    created_by text NOT NULL,
    updated_at timestamptz NOT NULL,
    updated_by text NOT NULL,
    row_version bigint NOT NULL,
    PRIMARY KEY (tenant_id, id),
    CONSTRAINT session_of_user FOREIGN KEY (tenant_id, user_id) REFERENCES fcon.user (tenant_id, id),
    CONSTRAINT session_id_hash_unique UNIQUE (tenant_id, id_hash)
);

CREATE INDEX session_user_id ON fcon.session (tenant_id, user_id);

-- Rows only added; sign-in removes those older than a day (decision 3). The
-- name is what was typed, lowercased: it need not be a user's.
CREATE TABLE fcon.sign_in_attempt (
    tenant_id text COLLATE pg_c_utf8 NOT NULL REFERENCES fcon.tenant (tenant_id),
    id uuid NOT NULL,
    name text COLLATE pg_c_utf8 NOT NULL,
    address text COLLATE pg_c_utf8 NOT NULL,
    outcome text NOT NULL CONSTRAINT sign_in_attempt_outcome CHECK (outcome IN ('succeeded', 'refused', 'waited')),
    created_at timestamptz NOT NULL,
    created_by text NOT NULL,
    PRIMARY KEY (tenant_id, id)
);

CREATE INDEX sign_in_attempt_name ON fcon.sign_in_attempt (tenant_id, name, created_at);
CREATE INDEX sign_in_attempt_address ON fcon.sign_in_attempt (tenant_id, address, created_at);
