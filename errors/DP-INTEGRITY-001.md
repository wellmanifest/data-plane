# DP-INTEGRITY-001: Event integrity or ordering failure

## Error DSL

```log-error-dsl
{"category":"CHAIN","causes":["Corruption, conflicting duplicate ID or missing predecessor."],"code":"DP-INTEGRITY-001","doNot":["Do not rewrite published history or skip a missing event."],"meaning":"An event cannot be admitted because identity, canonical bytes or chain disagree.","owner":"service:data-plane","relatedEventTypes":["error_raised","remediation_completed"],"remediation":["Stop the affected stream and reconcile against a trusted checkpoint."],"schema":"wellmanifest.logs/error/v1","severity":"ERROR","title":"Event integrity or ordering failure","verification":["Verify exact bytes, eventHash, previousHash and streamVersion."],"version":1}
```

## Situation

Corruption, conflicting duplicate ID or missing predecessor.

## Meaning

An event cannot be admitted because identity, canonical bytes or chain disagree.

## Safe resolution

Stop the affected stream and reconcile against a trusted checkpoint.

## Verification

Verify exact bytes, eventHash, previousHash and streamVersion.

## Do not

Do not rewrite published history or skip a missing event.

## Related events

error_raised, remediation_completed

