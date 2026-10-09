-- Driver-bound statement patterns, NOT a complete stored append implementation.
-- Trusted service does admission/schema/hash checks before COMMIT.
BEGIN;
SELECT set_config('app.tenant_id',$1,true);
-- Create head if needed, then lock. Caller verifies authority ownership.
INSERT INTO data_plane_es.stream_heads
 (tenant_id,stream_id,authority_id,authority_epoch,stream_version,event_hash)
VALUES ($1::uuid,$2::uuid,$3,$4::bigint,0,repeat('0',64))
ON CONFLICT DO NOTHING;
SELECT authority_id,authority_epoch,stream_version,event_hash
FROM data_plane_es.stream_heads
WHERE tenant_id=$1::uuid AND stream_id=$2::uuid FOR UPDATE;
-- Check exact command receipt under a transaction-scoped idempotency lock.
-- Validate expectedVersion + authorityEpoch + inputHash; append domain_events,
-- event_outbox and required synchronous projection and receipt in this transaction.
-- The following guarded update must affect one row, else ROLLBACK all inserts.
UPDATE data_plane_es.stream_heads
SET stream_version=$5::bigint,event_hash=$6
WHERE tenant_id=$1::uuid AND stream_id=$2::uuid
 AND authority_id=$3 AND authority_epoch=$4::bigint AND stream_version=$7::bigint;
-- COMMIT only after all inserts/checks succeeded. This file intentionally does
-- not include an unconditional COMMIT that could accept an incomplete command.
ROLLBACK;
