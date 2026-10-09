# DP-SOURCE-001: Required source unavailable

## Error DSL

```log-error-dsl
{"category":"DEPENDENCY","causes":["Connection failure, projection lag or unavailable local file."],"code":"DP-SOURCE-001","doNot":["Do not report empty data as a successful complete query."],"meaning":"A data source failed or did not reach the required freshness barrier.","owner":"service:data-plane","relatedEventTypes":["error_raised","remediation_completed"],"remediation":["Return an explicit unavailable/partial result and retry within policy."],"schema":"wellmanifest.logs/error/v1","severity":"ERROR","title":"Required source unavailable","verification":["Check source coverage, deadline and checkpoint."],"version":1}
```

## Situation

Connection failure, projection lag or unavailable local file.

## Meaning

A data source failed or did not reach the required freshness barrier.

## Safe resolution

Return an explicit unavailable/partial result and retry within policy.

## Verification

Check source coverage, deadline and checkpoint.

## Do not

Do not report empty data as a successful complete query.

## Related events

error_raised, remediation_completed

