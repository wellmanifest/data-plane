-- Reference core: PostgreSQL 16+. Run only in a new development database.
-- Not an application migration. Application must enforce hashes and resource ACL.
BEGIN;
CREATE SCHEMA data_plane;

CREATE TABLE data_plane.resource_versions (
    resource_id uuid PRIMARY KEY,
    tenant_id uuid NOT NULL,
    media_type text NOT NULL CHECK (length(media_type) BETWEEN 1 AND 255),
    sha256 text NOT NULL CHECK (sha256 ~ '^[0-9a-f]{64}$'),
    byte_length bigint NOT NULL CHECK (byte_length >= 0),
    content bytea NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    created_by text NOT NULL,
    UNIQUE (tenant_id, resource_id),
    CHECK (octet_length(content)::bigint = byte_length)
);
CREATE INDEX resource_versions_tenant_created
    ON data_plane.resource_versions (tenant_id, created_at DESC, resource_id DESC);

CREATE FUNCTION data_plane.reject_resource_update() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    RAISE EXCEPTION 'immutable resource: publish a new version' USING ERRCODE = '23000';
END;
$$;
CREATE TRIGGER resource_immutable BEFORE UPDATE ON data_plane.resource_versions
    FOR EACH ROW EXECUTE FUNCTION data_plane.reject_resource_update();

CREATE TABLE data_plane.entity_heads (
    tenant_id uuid NOT NULL,
    entity_id uuid NOT NULL,
    resource_id uuid NOT NULL,
    revision bigint NOT NULL CHECK (revision > 0),
    updated_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (tenant_id, entity_id),
    FOREIGN KEY (tenant_id, resource_id)
        REFERENCES data_plane.resource_versions (tenant_id, resource_id)
);

CREATE TABLE data_plane.process_runs (
    run_id uuid PRIMARY KEY,
    tenant_id uuid NOT NULL,
    operation_uri text NOT NULL,
    contract_digest text NOT NULL CHECK (contract_digest ~ '^[0-9a-f]{64}$'),
    state text NOT NULL CHECK (state IN ('queued','running','succeeded','failed','cancelled')),
    arguments jsonb NOT NULL CHECK (jsonb_typeof(arguments) = 'object'),
    outputs jsonb NOT NULL DEFAULT '[]' CHECK (jsonb_typeof(outputs) = 'array'),
    verification_resource_id uuid,
    cancel_requested boolean NOT NULL DEFAULT false,
    requested_by text NOT NULL,
    lease_owner text,
    lease_until timestamptz,
    fencing_token bigint NOT NULL DEFAULT 0 CHECK (fencing_token >= 0),
    attempt integer NOT NULL DEFAULT 0 CHECK (attempt >= 0),
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (tenant_id, run_id),
    FOREIGN KEY (tenant_id, verification_resource_id)
        REFERENCES data_plane.resource_versions (tenant_id, resource_id),
    CHECK (state <> 'succeeded' OR verification_resource_id IS NOT NULL),
    CHECK ((lease_owner IS NULL) = (lease_until IS NULL))
);
CREATE INDEX process_active ON data_plane.process_runs (tenant_id, created_at, run_id)
    WHERE state IN ('queued','running');

CREATE TABLE data_plane.outbox_events (
    event_id uuid PRIMARY KEY,
    tenant_id uuid NOT NULL,
    aggregate_id uuid NOT NULL,
    aggregate_revision bigint NOT NULL CHECK (aggregate_revision >= 0),
    event_type text NOT NULL,
    payload jsonb NOT NULL CHECK (jsonb_typeof(payload) = 'object'),
    created_at timestamptz NOT NULL DEFAULT now(),
    available_at timestamptz NOT NULL DEFAULT now(),
    delivered_at timestamptz,
    lease_owner text,
    lease_until timestamptz,
    fencing_token bigint NOT NULL DEFAULT 0 CHECK (fencing_token >= 0),
    attempt integer NOT NULL DEFAULT 0 CHECK (attempt >= 0),
    CHECK ((lease_owner IS NULL) = (lease_until IS NULL))
);
CREATE INDEX outbox_pending ON data_plane.outbox_events (tenant_id, available_at, event_id)
    WHERE delivered_at IS NULL;

CREATE TABLE data_plane.idempotency_records (
    tenant_id uuid NOT NULL,
    subject_id text NOT NULL,
    operation_uri text NOT NULL,
    idempotency_key varchar(128) NOT NULL,
    arguments_sha256 text NOT NULL CHECK (arguments_sha256 ~ '^[0-9a-f]{64}$'),
    response jsonb NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    expires_at timestamptz NOT NULL,
    PRIMARY KEY (tenant_id, subject_id, operation_uri, idempotency_key),
    CHECK (expires_at > created_at)
);
CREATE INDEX idempotency_expiry ON data_plane.idempotency_records (expires_at);

CREATE TABLE data_plane.resource_grants (
    tenant_id uuid NOT NULL,
    resource_id uuid NOT NULL,
    subject_id text NOT NULL,
    can_read boolean NOT NULL DEFAULT true,
    policy_revision bigint NOT NULL CHECK (policy_revision > 0),
    PRIMARY KEY (tenant_id, resource_id, subject_id),
    FOREIGN KEY (tenant_id, resource_id)
        REFERENCES data_plane.resource_versions (tenant_id, resource_id)
);

-- Runtime role must be NON-owner, NON-superuser, NOBYPASSRLS.
-- This is TENANT isolation, not subject-level ACL enforcement.
-- Application checks resource_grants in the same security context.
DO $$
DECLARE table_name text;
BEGIN
    FOREACH table_name IN ARRAY ARRAY[
        'resource_versions','entity_heads','process_runs',
        'outbox_events','idempotency_records','resource_grants'
    ] LOOP
        EXECUTE format('ALTER TABLE data_plane.%I ENABLE ROW LEVEL SECURITY', table_name);
        EXECUTE format('ALTER TABLE data_plane.%I FORCE ROW LEVEL SECURITY', table_name);
        EXECUTE format(
            'CREATE POLICY tenant_isolation ON data_plane.%I USING '
            '(tenant_id = nullif(current_setting(''app.tenant_id'', true), '''')::uuid) '
            'WITH CHECK (tenant_id = nullif(current_setting(''app.tenant_id'', true), '''')::uuid)',
            table_name
        );
    END LOOP;
END;
$$;

REVOKE ALL ON SCHEMA data_plane FROM PUBLIC;
REVOKE ALL ON ALL TABLES IN SCHEMA data_plane FROM PUBLIC;
REVOKE ALL ON ALL FUNCTIONS IN SCHEMA data_plane FROM PUBLIC;
-- Provision roles separately. Grant only needed tables/actions;
-- do not give resource UPDATE/DELETE or grants mutation to ordinary agents.
-- No auth credentials, login roles or broad grants are created by this example.
COMMIT;
