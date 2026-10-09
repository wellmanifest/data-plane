# DP-CONCURRENCY-001: Stream version or authority conflict

## Error DSL

```log-error-dsl
{"category":"CONCURRENCY","causes":["Another writer committed or authority changed."],"code":"DP-CONCURRENCY-001","doNot":["Do not overwrite the stream head or blindly change expectedVersion."],"meaning":"Command preconditions no longer match the authoritative stream.","owner":"service:data-plane","relatedEventTypes":["error_raised","remediation_completed"],"remediation":["Read the current authorized head and create a new plan if intent remains valid."],"schema":"wellmanifest.logs/error/v1","severity":"ERROR","title":"Stream version or authority conflict","verification":["Verify expectedVersion, authority epoch and command idempotency receipt."],"version":1}
```

## Situation

Another writer committed or authority changed.

## Meaning

Command preconditions no longer match the authoritative stream.

## Safe resolution

Read the current authorized head and create a new plan if intent remains valid.

## Verification

Verify expectedVersion, authority epoch and command idempotency receipt.

## Do not

Do not overwrite the stream head or blindly change expectedVersion.

## Related events

error_raised, remediation_completed

