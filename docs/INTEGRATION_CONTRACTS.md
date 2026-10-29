# Integration contracts — version 1

These contracts describe implemented clients and the optional verification service. The **AEM/tenant bridge and vendor-to-intake receiver are organization-specific services you must supply**. No fixture bridge is presented as a live integration. All live URLs and credentials come from reviewed server configuration, not model output or browser-entered URLs.

## Normalized event intake

`POST /api/intake`, `Content-Type: application/json`, maximum 64 KiB:

```json
{
  "event_id": "provider-unique-event-id",
  "source": "cloud_manager",
  "request": {
    "kind": "core",
    "environment": "stage",
    "objective": "release-readiness",
    "scope": "shared",
    "execution_id": "12345"
  }
}
```

Sources: `cloud_manager`, `monitoring`, `teams`, `scheduler`. Requests use the strict `RunRequest` schema in `backend/aaaem/contracts.py`; unknown fields are rejected. `site-onboarding` requires a validated `site_spec`. Schedules do not create factory requests automatically.

Headers:

```text
X-AAAEM-Timestamp: <Unix seconds>
X-AAAEM-Signature: <hex HMAC-SHA256(secret, timestamp + "." + exact_body_bytes)>
```

The timestamp must be within five minutes. The shared secret must contain at least 32 random characters and is read from `intake_secret_env` (default `AAAEM_INTAKE_SECRET`). Intake only accepts environments listed in `intake_environments`, default dev/stage. First accepted delivery returns `202 {"id":"RUN-…","created":true}`. A duplicate source/event ID and identical request returns the same run with `200`; changing the request under that identity returns `409`.

Example local submission after setting the secret in `.env`:

```bash
python scripts/submit_event.py --url http://localhost:8000 --file config/event.example.json
```

A native receiver must validate the original vendor's authentication/signature and authorize event scope **before** signing this normalized envelope. The source field alone is not proof of a vendor identity. The shared-secret sender can submit any allowed read workflow in enabled environments; do not expose that secret to Teams clients. Intake cannot approve or execute PRs. Notifications and native Teams Adaptive Card handlers are not implemented.

## Tenant/AEM read bridge

Configure a connection with `driver: "bridge"`, a reviewed HTTPS `base_url`, and a bearer `token_env`. Required endpoints:

- `GET /healthz`: authenticated read probe, return 2xx JSON when healthy.
- `POST /v1/read`: read-only operation; return the wrapper below. Mutations must not be exposed under this contract.

Example inheritance request:

```json
{
  "contract_version": 1,
  "operation": "aem.governance",
  "environment": "stage",
  "execution_id": "",
  "site_ids": [1],
  "sites": [
    {
      "id": 1,
      "content_root": "/content/example/us/en",
      "inheritance_exceptions": ["/content/example/us/en/local-offer"]
    }
  ]
}
```

Example response shape (replace timestamps/findings with actual reads):

```json
{
  "contract_version": 1,
  "operation": "aem.governance",
  "environment": "stage",
  "data": {
    "site_ids": [1],
    "complete": true,
    "captured_at": "2026-10-26T10:00:00+00:00",
    "findings": [
      {
        "id": "inheritance-1",
        "site_id": 1,
        "path": "/content/example/us/en/offers",
        "severity": "medium",
        "title": "Unexpected inheritance cancellation",
        "expected_exception": false
      }
    ],
    "coverage_note": "Reviewed live-copy roots and configured paths only"
  }
}
```

Read MSM relationships, inheritance cancellations and reviewed exception rules through your supported AEM API/service user. Return `complete=false` when any requested root is unavailable, denied, truncated or unsupported. `site_ids` must exactly identify checked scope. Record the actual capture time. The client verifies wrapper version, operation and environment, then labels its evidence `live:aem`. It rejects fixture provenance. It cannot independently prove that a bridge implementation told the truth; tenant bridge code and privileges require review.

A bridge can also normalize other named read operations when native APIs lack required tenant data:

| Operation | Expected `data` fields |
| --- | --- |
| `cloud_manager.execution` | `execution_id`, `revision`, `environment`, `deployment_completed`, `deployment_time`, `pipeline_status` |
| `monitoring.metrics` | Measured `requests`, `baseline_5xx_rate`, `current_5xx_rate`, `p95_ms`, `window_minutes`; omit unavailable values |
| `splunk.summary` | Bounded sanitized `patterns` containing `pattern` and `count`, `window_minutes` |
| `snyk.findings`, `sonar.findings`, `github.review` | `findings`, `complete`, `coverage_note`; optional provider-specific metadata |

The bridge owns correct tenant/environment authorization, pagination, freshness and source attribution. Do not translate an unknown revision into a guessed SHA, missing measurements into zeroes, or partial coverage into `complete=true`.

Use the native `verification` driver for browser results; the generic read bridge does not receive the expected release revision or site URL/page configuration and is not a substitute for the verification contract.

## Browser verification service

The included `backend/aaaem/verifier.py` implements `GET /healthz` and `POST /v1/verify`. Both require `Authorization: Bearer <AAAEM_VERIFIER_TOKEN>`. The application sends batches of at most four sites and renews its workflow lease between batches.

```json
{
  "contract_version": 1,
  "environment": "stage",
  "execution_id": "12345",
  "revision": "0123456789abcdef0123456789abcdef01234567",
  "sites": [
    {
      "id": 1,
      "url": "https://www.example.com",
      "pages": ["/", "/contact"],
      "revision_header": "X-AAAEM-Revision"
    }
  ]
}
```

Response shape:

```json
{
  "contract_version": 1,
  "input_mode": "live",
  "environment": "stage",
  "execution_id": "12345",
  "revision": "0123456789abcdef0123456789abcdef01234567",
  "captured_at": "2026-10-26T10:05:00+00:00",
  "complete": true,
  "revision_verified": true,
  "sites": [
    {
      "id": 1,
      "passed": 16,
      "total": 16,
      "complete": true,
      "revision_verified": true,
      "observed_revisions": ["0123456789abcdef0123456789abcdef01234567", "0123456789abcdef0123456789abcdef01234567"],
      "blocked_hosts": [],
      "pages": []
    }
  ]
}
```

This is an illustrative shape, not a successful scan record. The real service supplies per-page checks and actual counts. Echoed `revision` and `execution_id` associate a request; **the measured page response headers** establish revision verification. All configured pages must serve the expected revision. No expected revision is injected into site requests. A deployment can finish successfully while site checks fail or revision proof remains inconclusive.

Checks: navigation/HTTP status, title, document language, canonical presence, exactly one H1, declared image alt text and button names, desktop horizontal overflow, and at most five same-host links per page. These are basic heuristics; for example, an `aria-labelledby` attribute is detected but its full accessibility-tree correctness is not audited. Each site has at most 10 configured paths. One batch runs at a time with a 45-second budget; busy service returns 429. Blocked resources or unfinished site scans mean incomplete coverage. No form submissions, authenticated journeys, recursive crawling, mutations or screenshot retention are performed.

The client rejects mismatched wrapper version, environment, execution or revision. The workflow validates exact site coverage, positive integer counts, freshness, measured revision proof and deployment timing. Governance consumes these bounded checks without requiring a release revision.

## Failure semantics

Missing settings produce unavailable evidence rather than demo fallback. Authentication denial, rate limits, network/TLS failure, malformed JSON, oversized responses and scope mismatches remain visible as safe codes. Errors do not include credential-bearing raw response bodies. Workflows may be `blocked`, `inconclusive`, or `failed`, depending on which evidence was obtained. `reachable` is a connection probe result, not a release verification result.

Run retries create a fresh evidence attempt. Expired worker leases are recovered with bounded attempts. External PR writes have a separate approval/execution record and reconcile unknown outcomes using a stable branch identity.

## Primary adapter references

- Adobe Cloud Manager authentication: https://developer.adobe.com/experience-cloud/cloud-manager/guides/getting-started/authentication/authentication
- Cloud Manager API: https://developer.adobe.com/experience-cloud/cloud-manager/reference/api
- New Relic NRQL/NerdGraph: https://docs.newrelic.com/docs/apis/nerdgraph/examples/nerdgraph-nrql-tutorial/
- Splunk search API: https://help.splunk.com/en/splunk-enterprise/leverage-rest-apis/rest-api-tutorials/10.4/rest-api-tutorials/creating-searches-using-the-rest-api
- Snyk issues: https://docs.snyk.io/developer-tools/snyk-api/reference/issues
- OpenID Connect: https://openid.net/specs/openid-connect-core-1_0.html
- Playwright browser contexts: https://playwright.dev/python/docs/api/class-browsercontext

API availability, tenant permissions and response fields still require acceptance testing against your systems.
