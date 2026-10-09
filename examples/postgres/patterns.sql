-- Patterns only, not a file to execute as a migration.
-- $1 etc are driver-bound values; each transaction sets app.tenant_id first.

-- Tenant context; caller obtains $1 from verified authentication.
SELECT set_config('app.tenant_id', $1, true);

-- Resolve pointer on PRIMARY with applicable subject/resource authorization.
SELECT resource_id, revision
FROM data_plane.entity_heads WHERE tenant_id = $1::uuid AND entity_id = $2::uuid;

-- CAS update: zero rows => REVISION_CONFLICT or NOT_FOUND after authorized lookup.
UPDATE data_plane.entity_heads
SET resource_id = $3::uuid, revision = revision + 1, updated_at = now()
WHERE tenant_id = $1::uuid AND entity_id = $2::uuid AND revision = $4::bigint
RETURNING resource_id, revision;

-- First head: expectedRevision must be "0". Unique conflict is a revision conflict.
INSERT INTO data_plane.entity_heads (tenant_id, entity_id, resource_id, revision)
VALUES ($1::uuid, $2::uuid, $3::uuid, 1)
ON CONFLICT DO NOTHING RETURNING resource_id, revision;

-- Serialize an idempotency scope using an application-computed signed int64 hash.
-- Hash collisions cause extra serialization, not incorrect matching;
-- the exact composite PRIMARY KEY remains authoritative.
SELECT pg_advisory_xact_lock($1::bigint);
-- Then read exact key, compare canonical arguments hash, mutate, insert result,
-- append outbox in THIS transaction. Never hold lock across external calls.

-- Claim outbox rows for one authenticated tenant in a short transaction.
WITH candidates AS (
    SELECT event_id FROM data_plane.outbox_events
    WHERE tenant_id = $1::uuid AND delivered_at IS NULL
      AND available_at <= now() AND (lease_until IS NULL OR lease_until < now())
    ORDER BY available_at, event_id FOR UPDATE SKIP LOCKED LIMIT $2
)
UPDATE data_plane.outbox_events e
SET lease_owner = $3, lease_until = now() + interval '30 seconds',
    fencing_token = fencing_token + 1, attempt = attempt + 1
FROM candidates c WHERE e.event_id = c.event_id
RETURNING e.*;

-- Commit, send event, then ACK in a NEW tenant-scoped transaction.
UPDATE data_plane.outbox_events
SET delivered_at = now(), lease_owner = NULL, lease_until = NULL
WHERE tenant_id = $1::uuid AND event_id = $2::uuid
  AND lease_owner = $3 AND fencing_token = $4::bigint
  AND lease_until > now() AND delivered_at IS NULL;

-- Keyset pagination (an authz predicate/join is also required by the handler).
SELECT resource_id, media_type, sha256, byte_length, created_at
FROM data_plane.resource_versions
WHERE tenant_id = $1::uuid AND (created_at, resource_id) < ($2::timestamptz, $3::uuid)
ORDER BY created_at DESC, resource_id DESC LIMIT $4;
