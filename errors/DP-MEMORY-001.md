# DP-MEMORY-001: Memory or query budget exceeded

## Error DSL

```log-error-dsl
{"category":"RESOURCE","causes":["Too many keys, sources, rows or response bytes."],"code":"DP-MEMORY-001","doNot":["Do not remove limits or load the complete database into memory."],"meaning":"The requested operation exceeded a configured bounded resource budget.","owner":"service:data-plane","relatedEventTypes":["error_raised","remediation_completed"],"remediation":["Reduce the page or use a registered projection/export process."],"schema":"wellmanifest.logs/error/v1","severity":"ERROR","title":"Memory or query budget exceeded","verification":["Measure peak memory and verify the bounded query succeeds."],"version":1}
```

## Situation

Too many keys, sources, rows or response bytes.

## Meaning

The requested operation exceeded a configured bounded resource budget.

## Safe resolution

Reduce the page or use a registered projection/export process.

## Verification

Measure peak memory and verify the bounded query succeeds.

## Do not

Do not remove limits or load the complete database into memory.

## Related events

error_raised, remediation_completed

