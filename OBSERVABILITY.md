# Observability

How the API reports what it is doing, where to look when production misbehaves,
and the AWS configuration behind it. Added 2026-09-26. The webapp's side is in
`pickem-webapp/OBSERVABILITY.md`.

## Why this exists

Two weeks of prod logs (Sep 12–26, 2026) showed:

| Symptom | Cause | Fix |
|---|---|---|
| Random 500s, worse on Sundays | peewee's connection pool handed out connections Neon had already dropped while the Lambda was frozen ("SSL connection has been closed unexpectedly": ~116 of ~143 5xx) | Pool removed; connection is pinged before reuse (below) |
| "Cannot connect to server" | Lambda timeouts and crashes came back as API Gateway 502/504s with no CORS headers, which the browser hides as `Network Error` | CORS headers on gateway error responses; Lambda timeout 28s |
| Users logged out daily | JWT signing key (`dev/oauth`) rotated **daily**, and tokens were only checked against the newest key | Rotation changed to every 30 days |
| Slow first loads | ~10% of requests are cold starts, averaging ~3.2–3.5s of startup | Not fixed yet; see [Open issues](#open-issues) |

## What the API emits

### Structured logs

Every log line is one JSON object (`src/config/logger.py`, `JsonFormatter`), so
CloudWatch Logs Insights can filter on fields directly. Lines logged during a
request carry `request_id`.

Pass structured fields with:

```python
self.logger.info("something happened", extra={"fields": {"league_id": 3}})
```

### One summary line per request

The middleware in `src/app.py` writes `message = "request completed"`,
`type = "request"` with:

| Field | Meaning |
|---|---|
| `method`, `route`, `path` | `route` is the template (`/results/{league_id}/{year}/user-picks`); use it for grouping |
| `status`, `duration_ms` | Status code, and time spent inside the app |
| `db_ms`, `db_queries`, `db_connect_ms` | Time in SQL, number of queries, time spent opening a connection |
| `cold_start` | First request handled by this Lambda container |
| `user` | Token subject, when the route is authenticated |
| `request_id` | Client-sent `X-Request-ID` if well-formed, else the API Gateway request id |
| `apigw_request_id` | Joins to the API Gateway access logs |
| `lambda_request_id` | Joins to Lambda `REPORT` lines (init duration, memory) |

5xx summaries are logged at `ERROR`, everything else at `INFO`.

### Request IDs

- Every response carries an `X-Request-ID` header (exposed to the browser via CORS).
- Unexpected errors return `{"detail": "An unexpected error occurred", "requestId": "..."}`.
  The exception text stays in the log and is never sent to the client.
- The webapp sends its own ID on every request, so a failure seen in the
  browser can be found in CloudWatch by that ID.

### Metrics (CloudWatch Embedded Metric Format)

The request summary line also publishes metrics. CloudWatch extracts them from
the log, with no API calls. They are emitted only inside Lambda
(`AWS_LAMBDA_FUNCTION_NAME` set).

- Namespace `Pickem/Api`, dimension `Service` = Lambda function name
- `Requests`, `ServerErrors`, `ClientErrors`, `Latency` (ms), `DbTime` (ms),
  `ColdStarts`, `ClientReportedErrors`

Metrics are service-level only on purpose: a `Route` dimension would bill
each route as a separate metric (~$0.30/metric/month × ~60 routes × 6 metrics).
Get per-route numbers from Logs Insights instead.

### Other structured events

| `type` | Where | Fields |
|---|---|---|
| `login_failed` | `auth_service.login` | `reason` (`unknown_user` / `bad_password`), `username` |
| `client_event` | `/telemetry/client-events` | See below |
| n/a (`message = "discarding database connection"`) | `db_connection.py` | `reason`: a dead connection was caught before use |
| n/a (`message = "opened database connection"`) | `db_connection.py` | `db_connect_ms` |

### Browser telemetry endpoint

`POST /api/telemetry/client-events` (`src/components/telemetry/`) accepts up to
25 events per batch from the webapp and logs each one as
`type = "client_event"`, with `client_event` set to `api_error`, `api_slow`,
`js_error` or `render_error`. It is unauthenticated, because it has to work
when auth is what's broken, so every field is length-bounded. It never touches
the database.

## Database connections

`src/config/db_connection.py`, `LambdaPostgresqlDatabase`:

- **No client-side pool.** A Lambda container serves one request at a time,
  and the Neon `-pooler` host already pools on the server side.
- **One connection per container, reused across requests.** Opening one costs
  ~300ms of TLS and auth.
- **Checked after 10s idle.** The middleware calls `database.discard_if_dead()`
  at the start of each request. If the connection has been idle longer than
  `_PING_AFTER_IDLE_S`, it runs `SELECT 1`, and discards the connection if that
  fails or if the connection is left in a failed transaction. The next query
  reconnects (peewee autoconnect).
- **Discarded after connection errors.** If a request fails with
  `OperationalError` or `InterfaceError`, the connection is discarded so the
  next request doesn't inherit it.
- **`thread_safe=False`.** FastAPI runs sync dependencies on a worker thread.
  A thread-local connection there would be a second, leaked connection.
- **`connect_timeout=5`.**
- **No eager connect.** Routes that never query (`/ping`, telemetry) never
  open a connection.

## Secrets caching

`src/integrations/secret_service.py` caches secrets for 5 minutes
(`DEFAULT_MAX_AGE_S`) and reuses one boto3 client. Before this, every
authenticated request called Secrets Manager.

JWT handling in `src/security/oauth_service.py`:

- **Signing** always fetches the current key (`max_age_s=0`), so a token is
  never signed with a pre-rotation key.
- **Verifying** uses the cached key. On a signature failure it re-fetches once,
  so a rotation can't cause false 401s. Expired tokens are rejected without a
  re-fetch.

## Cold start trims

`playwright` (scraper) and `imageio` (team image) are imported inside the
functions that use them, not at module load. See [Open issues](#open-issues)
for why cold starts are still slow.

## AWS configuration

**None of this is in IaC.** CI only runs `update-function-code`. These were
applied by hand with the AWS CLI on 2026-09-26 (account 881413588329,
us-east-1).

| Resource | Setting |
|---|---|
| REST API `pyxuj4rmh4` (prod) and `u3wc2hb3q4` (dev), stage `pickem` | Gateway responses `DEFAULT_4XX` / `DEFAULT_5XX` return `Access-Control-Allow-Origin: *`, `Access-Control-Allow-Headers: *`, `Access-Control-Expose-Headers: X-Request-ID` |
| Lambda `pickem-api_prod`, `pickem-api_dev` | Timeout **28s** (was 900s; API Gateway gives up at 29s). Memory **1024MB** (was 512MB) |
| Prod stage access logs | `/aws/apigateway/pickem-api_prod/access`, JSON, 30-day retention |
| Log retention | `/aws/lambda/pickem-api_prod` and `_dev`: 90 days. `API-Gateway-Execution-Logs_pyxuj4rmh4/pickem`: 30 days |
| Secret `dev/oauth` (JWT signing key) | Rotation every **30 days** (was daily). Next: 2026-10-26 |
| SNS `Pickem_500_alarm_notification` | Email subscription to brayk2@gmail.com |
| Removed | Alarm "Pickem Error Listener": it watched the non-prod API and had no subscribers |

### Alarms (all notify the SNS topic on ALARM and OK)

| Alarm | Condition |
|---|---|
| `pickem-prod-api-5xx` | API Gateway `5XXError` ≥ 5 in 5 min |
| `pickem-prod-api-latency-p95` | API Gateway p95 `Latency` > 3s in 2 of 3 five-minute periods |
| `pickem-prod-lambda-errors` | Lambda `Errors` ≥ 1 in 5 min (crash, out of memory, timeout) |
| `pickem-prod-lambda-near-timeout` | Lambda max `Duration` > 20s |
| `pickem-prod-client-reported-errors` | `Pickem/Api` `ClientReportedErrors` ≥ 10 in 5 min |

### Dashboard

CloudWatch dashboard **`pickem-api-prod`**:
- API Gateway requests, errors and latency
- Lambda health and duration
- Cold starts and DB time
- Browser-reported problems
- Log-query tables: slowest routes, recent 5xx, cold start init time, error
  types, login failures, and gateway errors from the access logs

### Undo cheatsheet

```bash
aws lambda update-function-configuration --function-name pickem-api_prod --timeout 900 --memory-size 512
aws apigateway delete-gateway-response --rest-api-id pyxuj4rmh4 --response-type DEFAULT_5XX   # then create-deployment
aws secretsmanager rotate-secret --secret-id dev/oauth --rotation-rules AutomaticallyAfterDays=1 --no-rotate-immediately
```

Always pass `--no-rotate-immediately` when changing rotation rules. Without
it, the key rotates on the spot and every user is logged out.

## Debugging recipes (CloudWatch Logs Insights)

Run these against log group `/aws/lambda/pickem-api_prod` unless noted.

**Slowest routes**
```
filter type = "request"
| stats count(*) as requests, pct(duration_ms, 95) as p95_ms, avg(db_ms) as avg_db_ms,
        avg(db_queries) as avg_queries, sum(status >= 500) as errors_5xx by method, route
| sort p95_ms desc
```

**Everything about one request** (ID from the browser, `X-Request-ID`, or a user's error)
```
filter request_id = "PASTE-ID" | sort @timestamp asc
```

**Recent 5xx with the exception**
```
filter level = "ERROR" | fields @timestamp, route, status, exception_type, exception, request_id
| sort @timestamp desc | limit 50
```

**Cold starts**
```
filter @type = "REPORT"
| stats count(*) as invocations, count(@initDuration) as cold_starts,
        avg(@initDuration) as avg_init_ms by bin(1h)
```

**Is the database the slow part?**
```
filter type = "request" and duration_ms > 1000
| fields route, duration_ms, db_ms, db_queries, db_connect_ms, cold_start
| sort duration_ms desc
```

**Dead connections caught before use**
```
filter message = "discarding database connection" | stats count(*) by reason, bin(1d)
```

**What browsers are seeing**
```
filter type = "client_event"
| stats count(*) by client_event, route, status, error_code | sort `count(*)` desc
```
A `client_event = "api_error"` with no `status` and `error_code = "ERR_NETWORK"`
means the browser never got a readable response: a gateway error, a dropped
connection, or the user was offline (`online` field).

**Login failures**
```
filter type = "login_failed" | stats count(*) by reason, username
```

**Gateway errors the Lambda never logged** (log group `/aws/apigateway/pickem-api_prod/access`)
```
filter status >= 500
| fields requestTime, method, path, status, errorType, errorMessage, integrationError, integrationLatency
```
`integrationLatency` near 29000 means a timeout. `errorType` `INTEGRATION_FAILURE`
or `INTEGRATION_TIMEOUT` means the Lambda crashed or took too long.

## Open issues

- **Cold starts are ~3.5s and are disk-bound, not CPU-bound.** Doubling memory
  didn't help. About 1.5s goes to imports before `db_models`, and about 2s goes
  from fetching the DB secret to the first request. The deployment zip is 85MB.
  `playwright` (~108MB unpacked) and `numpy`/`Pillow` (via `imageio`) account
  for most of it and only serve the scraper and team-image routes. Moving
  those into their own Lambda should cut startup substantially. Provisioned
  concurrency on game days is the paid alternative.
- **Admin page 500s:** IAM `AccessDenied` on `scheduler:ListSchedules` and
  `states:ListTagsForResource` / `states:ListExecutions`. Prod also calls
  `pickem-init-week_dev`.
- **Case-sensitive usernames:** many `unknown_user` login failures differ only
  by capitalization (phone keyboards).
- **The JWT key still invalidates all sessions on rotation**, now monthly.
  Accepting `AWSPREVIOUS` during verification would make rotation invisible to
  users.
- **Sentry** (error grouping with stack traces, frontend-to-backend tracing)
  was considered and deferred.
