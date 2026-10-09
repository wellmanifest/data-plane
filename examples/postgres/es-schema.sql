-- Self-contained reference schema, PostgreSQL 16+. No production roles created.
-- DDL alone does not implement append authorization or CAS: use trusted handlers.
BEGIN;
CREATE SCHEMA data_plane_es;
CREATE TABLE data_plane_es.stream_heads (
 tenant_id uuid NOT NULL, stream_id uuid NOT NULL,
 authority_id text NOT NULL, authority_epoch bigint NOT NULL CHECK(authority_epoch>0),
 stream_version bigint NOT NULL DEFAULT 0 CHECK(stream_version>=0),
 event_hash text NOT NULL CHECK(event_hash ~ '^[0-9a-f]{64}$'),
 PRIMARY KEY(tenant_id,stream_id)
);
CREATE TABLE data_plane_es.domain_events (
 event_id uuid PRIMARY KEY, tenant_id uuid NOT NULL, stream_id uuid NOT NULL,
 stream_version bigint NOT NULL CHECK(stream_version>0),
 event_type text NOT NULL, schema_version integer NOT NULL CHECK(schema_version>0),
 process_uri text NOT NULL, command_id uuid NOT NULL, correlation_id uuid NOT NULL,
 causation_id uuid, occurred_at timestamptz NOT NULL,
 authority_id text NOT NULL, authority_epoch bigint NOT NULL CHECK(authority_epoch>0),
 plan_hash text NOT NULL CHECK(plan_hash ~ '^[0-9a-f]{64}$'),
 input_hash text NOT NULL CHECK(input_hash ~ '^[0-9a-f]{64}$'),
 previous_hash text NOT NULL CHECK(previous_hash ~ '^[0-9a-f]{64}$'),
 event_hash text NOT NULL CHECK(event_hash ~ '^[0-9a-f]{64}$'),
 canonical_event bytea NOT NULL CHECK(octet_length(canonical_event)<=16384),
 UNIQUE(tenant_id,stream_id,stream_version), UNIQUE(tenant_id,event_id),
 FOREIGN KEY(tenant_id,stream_id) REFERENCES data_plane_es.stream_heads
);
CREATE TABLE data_plane_es.event_outbox (
 tenant_id uuid NOT NULL, consumer_id text NOT NULL, event_id uuid NOT NULL,
 delivered_at timestamptz, lease_owner text, lease_until timestamptz,
 fencing_token bigint NOT NULL DEFAULT 0, attempt integer NOT NULL DEFAULT 0,
 PRIMARY KEY(tenant_id,consumer_id,event_id),
 FOREIGN KEY(tenant_id,event_id) REFERENCES data_plane_es.domain_events(tenant_id,event_id),
 CHECK((lease_owner IS NULL)=(lease_until IS NULL)),
 CHECK(fencing_token>=0 AND attempt>=0)
);
CREATE INDEX outbox_unacked ON data_plane_es.event_outbox(tenant_id,consumer_id,event_id)
 WHERE delivered_at IS NULL;
CREATE TABLE data_plane_es.projection_checkpoints (
 tenant_id uuid NOT NULL, projection_id text NOT NULL, projector_version text NOT NULL,
 source_id text NOT NULL, stream_id uuid NOT NULL,
 stream_version bigint NOT NULL CHECK(stream_version>=0),
 event_hash text NOT NULL CHECK(event_hash ~ '^[0-9a-f]{64}$'),
 authority_id text NOT NULL, authority_epoch bigint NOT NULL CHECK(authority_epoch>0),
 updated_at timestamptz NOT NULL DEFAULT now(),
 PRIMARY KEY(tenant_id,projection_id,projector_version,source_id,stream_id)
);
CREATE TABLE data_plane_es.command_receipts (
 tenant_id uuid NOT NULL, subject_id text NOT NULL, operation_uri text NOT NULL,
 idempotency_key varchar(128) NOT NULL,
 input_hash text NOT NULL CHECK(input_hash ~ '^[0-9a-f]{64}$'),
 result_bytes bytea NOT NULL CHECK(octet_length(result_bytes)<=32768),
 created_at timestamptz NOT NULL DEFAULT now(), expires_at timestamptz NOT NULL,
 PRIMARY KEY(tenant_id,subject_id,operation_uri,idempotency_key), CHECK(expires_at>created_at)
);
CREATE TABLE data_plane_es.aggregate_snapshots (
 tenant_id uuid NOT NULL, stream_id uuid NOT NULL,
 stream_version bigint NOT NULL CHECK(stream_version>=0),
 projector_version text NOT NULL, state_resource_id uuid NOT NULL,
 state_sha256 text NOT NULL CHECK(state_sha256 ~ '^[0-9a-f]{64}$'),
 source_event_hash text NOT NULL CHECK(source_event_hash ~ '^[0-9a-f]{64}$'),
 created_at timestamptz NOT NULL DEFAULT now(),
 PRIMARY KEY(tenant_id,stream_id,projector_version,stream_version)
 -- Resource resolver must validate existence, tenant, hash and retention.
);
CREATE TABLE data_plane_es.audit_events (
 tenant_id uuid NOT NULL, stream_name text NOT NULL,
 sequence bigint NOT NULL CHECK(sequence BETWEEN 1 AND 9007199254740991),
 event_id text NOT NULL, contract_sha256 text NOT NULL,
 event_hash text NOT NULL CHECK(event_hash ~ '^[0-9a-f]{64}$'),
 previous_hash text NOT NULL CHECK(previous_hash ~ '^[0-9a-f]{64}$'),
 canonical_event bytea NOT NULL CHECK(octet_length(canonical_event)<=65536),
 PRIMARY KEY(tenant_id,stream_name,sequence), UNIQUE(tenant_id,event_id)
 -- Published canonical event bytes never change; export state belongs separately.
);
CREATE TABLE data_plane_es.audit_export_checkpoints (
 tenant_id uuid NOT NULL, stream_name text NOT NULL,
 sequence bigint NOT NULL CHECK(sequence>=0), event_hash text NOT NULL,
 PRIMARY KEY(tenant_id,stream_name)
);
CREATE FUNCTION data_plane_es.reject_history_change() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN RAISE EXCEPTION 'immutable history; append a successor event' USING ERRCODE='23000'; END;
$$;
CREATE TRIGGER immutable_domain BEFORE UPDATE OR DELETE ON data_plane_es.domain_events
 FOR EACH ROW EXECUTE FUNCTION data_plane_es.reject_history_change();
CREATE TRIGGER immutable_audit BEFORE UPDATE OR DELETE ON data_plane_es.audit_events
 FOR EACH ROW EXECUTE FUNCTION data_plane_es.reject_history_change();
DO $$
DECLARE n text;
BEGIN
 FOREACH n IN ARRAY ARRAY['stream_heads','domain_events','event_outbox','projection_checkpoints','command_receipts','aggregate_snapshots','audit_events','audit_export_checkpoints'] LOOP
  EXECUTE format('ALTER TABLE data_plane_es.%I ENABLE ROW LEVEL SECURITY',n);
  EXECUTE format('ALTER TABLE data_plane_es.%I FORCE ROW LEVEL SECURITY',n);
  EXECUTE format('CREATE POLICY tenant_isolation ON data_plane_es.%I USING (tenant_id = nullif(current_setting(''app.tenant_id'',true),'''')::uuid) WITH CHECK (tenant_id = nullif(current_setting(''app.tenant_id'',true),'''')::uuid)',n);
 END LOOP;
END;
$$;
REVOKE ALL ON SCHEMA data_plane_es FROM PUBLIC;
REVOKE ALL ON ALL TABLES IN SCHEMA data_plane_es FROM PUBLIC;
REVOKE ALL ON ALL FUNCTIONS IN SCHEMA data_plane_es FROM PUBLIC;
COMMIT;
