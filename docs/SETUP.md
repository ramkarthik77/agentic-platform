# Configure AABTS Platform

The repository runs end to end locally with synthetic integrations. To use your systems, configure the files below and validate a stage workflow before enabling recurring work. All paths in this guide are relative to the repository root; run the scripts there.

## 1. Keep runtime, connections and inference separate

| Setting | Values | Meaning |
| --- | --- | --- |
| `AABTS_MODE` | `local`, `production` | Trusted loopback operator, or OIDC-authenticated hosted workspace |
| `AABTS_INTEGRATION_MODE` | `fixture`, `live` | Synthetic enterprise inputs, or configured live read adapters |
| `AABTS_MODEL_PROVIDER` | `fixture`, `bedrock`, `openai_compatible` | Deterministic text, Bedrock inference, or your approved compatible gateway |

Live integrations do not require a model subscription. Selecting Bedrock alone does not connect enterprise systems. Model inference is billable when enabled. Evidence is sent to the selected model endpoint; review that data flow with your platform owner.

## 2. Create your configuration

```bash
cp .env.example .env
cp config/workspace.example.json config/local.json
cp config/registry.example.json config/registry.local.json
```

Set `registry_file` in `config/local.json` to `config/registry.local.json`. Replace the example registry with your own sites. In `.env` set:

```dotenv
AABTS_MODE=local
AABTS_INTEGRATION_MODE=live
AABTS_CONFIG_FILE=config/local.json
DATABASE_URL=sqlite:///.data/aaaem-live.db
AABTS_MODEL_PROVIDER=fixture
```

Never reuse a fixture database for live evidence. The application rejects this mismatch. Configuration and registry examples include JSON schemas for editor validation. Secrets are supplied in `.env` locally or injected by your hosting environment; JSON fields such as `token_env` contain **variable names**, not values. Local files, databases and credentials are ignored by Git. Review `git status` before pushing tenant-specific files.

The server only reads configuration at startup. Restart all API and worker processes after edits. Validate before starting:

```bash
python scripts/doctor.py
python scripts/serve.py
```

The doctor confirms shape and missing fields. It does not call external services. **Integrations → Check connection** performs a read probe and records its time and result. Only an admin can invoke this in hosted mode.

## 3. Configure the endpoints you need

Each `environments.dev|stage|production.connections` entry is separate. Copy stage mappings deliberately; a Cloud Manager environment ID and monitoring query must identify the same environment. Unconfigured services are shown as unavailable; live mode never substitutes fixture evidence.

| Connection | Driver and endpoint | Required configuration / secret |
| --- | --- | --- |
| Cloud Manager | `cloud_manager`, `https://cloudmanager.adobe.io` | Program, pipeline and environment IDs; Adobe client ID/organization header references; OAuth token endpoint and scopes from Developer Console; client secret reference |
| New Relic | `new_relic`, your region's NerdGraph endpoint | Account ID; approved bounded NRQL; `NEW_RELIC_API_KEY` |
| Splunk | `splunk`, HTTPS management API origin, including port if applicable | Approved summary SPL; `SPLUNK_TOKEN` with search-only permissions |
| Snyk | `snyk`, your region's REST API base ending in `/rest` | Organization ID; supported API date in `api_version`; `SNYK_TOKEN` |
| Sonar | `sonar`, SonarQube/SonarCloud API origin | Project key; `SONAR_TOKEN` |
| GitHub | `github`, `https://api.github.com` or your supported API base | `owner/repository`, branch and exact `review_paths`; `AABTS_GITHUB_TOKEN` |
| AEM metadata | `bridge`, your internal bridge HTTPS base | `AEM_BRIDGE_TOKEN`; the contract in INTEGRATION_CONTRACTS.md |
| Browser verification | `verification`, your verification service HTTPS base | `AABTS_VERIFIER_TOKEN`; set timeout to 60 seconds |

All base URLs require HTTPS and reject embedded credentials, query strings and fragments. The client verifies TLS, refuses redirects, bounds responses to 2 MB and uses per-connection timeouts. A private CA can be provided through `AABTS_CA_BUNDLE`. Proxy environment variables are deliberately not inherited; use your network routing or implement an explicitly reviewed transport.

Cloud Manager supports a static bearer token through `token_env`, or client-credentials OAuth through `parameters.oauth`. Use the exact token endpoint/scopes assigned to your Adobe integration, plus `x-api-key` and `x-gw-ims-org-id` headers. A completed pipeline must match the configured program, pipeline and environment. If its response does not contain one unambiguous commit ID, release verification remains inconclusive. You can supply a reviewed `bridge` adapter for tenant-specific execution/build metadata; the generic bridge client is included, not a tenant-specific bridge server.

New Relic queries must be server-configured reads with a `SINCE` window. Return one aggregate row with the aliases you need: `requests`, `baseline_5xx_rate`, `current_5xx_rate`, `p95_ms`. Missing measurements remain missing. For example, adapt this to your application's actual entity/environment dimensions:

```sql
SELECT count(*) AS requests,
  percentage(count(*), WHERE httpResponseCode LIKE '5%') AS current_5xx_rate
FROM Transaction WHERE appName = 'YOUR_STAGE_APPLICATION'
SINCE 30 minutes ago
```

Splunk expects aggregated `pattern` and `count` columns, never raw logs. The adapter supplies a 30-minute window and permits at most 100 rows; configured searches with known write commands are rejected. Service permissions must independently prevent writes. Redaction is limited to common credential/email patterns, so aggregate and sanitize at the source too.

Snyk/Sonar pagination is bounded by `max_pages` (default 5, maximum 20). Truncated results are incomplete. GitHub review reads at most 20 configured files from one exact commit, and applies three heuristic rules; it does not inspect an arbitrary PR diff or implement fixes.

## 4. Register real sites and verify the served revision

Each site needs a stable positive ID, name, market, theme, and an environment-to-URL map. Configure 1–10 page paths per site, an optional AEM content root and reviewed inheritance exceptions. The registry supports up to 1,000 entries; a single run supports at most 250 sites. Split larger estates into selected-scope runs.

`revision_header` identifies the HTTP response header your deployment emits, for example `X-AABTS-Revision`. Its value must be the exact deployed commit ID on **every configured page**. It must come from the application/deployment, not an edge rule that echoes a caller's requested value. No expected revision is sent as a browser request header.

A release is `verified` only when execution/environment/revision, exact site scope, positive check counts, deployment completion, measured response-header revision, and fresh complete browser evidence agree. Missing revision headers or build metadata produce `inconclusive`, even if page checks pass. Evidence older than two hours, from before the deployment finished, or over one minute in the future cannot verify a release. Governance checks can run without a release revision.

The live dependency map is conservative: non-selected runs check all registry sites with a URL in that environment. This is not proof of deploy-to-site impact. Explicit selections are operator-defined scope, also not a proven dependency graph.

## 5. Start the separate browser worker

```bash
python -m playwright install --with-deps chromium
python scripts/serve_verifier.py
```

Set a random 32+ character `AABTS_VERIFIER_TOKEN` and comma-separated exact `AABTS_VERIFIER_ALLOWED_HOSTS` in `.env`. Include legitimate asset/CDN hosts as well as page hosts. The scanner accepts only public HTTPS destinations, rejects private DNS addresses, blocks service workers/WebSockets, and aborts non-GET/HEAD requests. Missing host permissions make coverage incomplete. Private author/AEM endpoints belong behind the metadata bridge, not this public-site scanner.

Expose this service behind an authenticated-network HTTPS proxy, or pass `--ssl-certfile` and `--ssl-keyfile` for local TLS. The application integration URL must use HTTPS. `Dockerfile.verifier` includes Chromium; it is a separate service from the main application image. Use an isolated subnet/egress policy without access to cloud metadata or internal services. Application DNS checks alone are not an SSRF boundary against DNS changes.

The worker scans batches of four sites, with one batch in flight and a 45-second budget. It checks desktop navigation, basic SEO/accessibility, overflow, and at most five same-host links per configured page. Timed-out or blocked batches are incomplete. It does not run functional business journeys, interact with forms, capture a screenshot archive, or certify accessibility.

## 6. Configure enterprise sign-in

Hosted mode requires PostgreSQL, `AABTS_INTEGRATION_MODE=live`, an HTTPS origin and complete OIDC settings. Set explicit authorization, token and JWKS URLs from your identity provider; discovery is not fetched automatically. Register the exact callback:

```text
https://YOUR_WORKSPACE_HOST/auth/callback
```

Use authorization code flow, a confidential client secret, PKCE S256, and RS256 ID tokens. Configure a list-valued group/app-role claim in the **ID token**. `group_claim` defaults to `groups`; nested claims and provider group-overage APIs are not resolved. For Entra ID, use the exact group IDs or app-role names actually emitted by your tenant.

Map groups to `roles` and `environments` in `auth.group_grants`:

| Role | Allowed behavior |
| --- | --- |
| reader | Inspect permitted-environment runs, reports and setup readiness |
| operator | Submit/cancel/retry runs; prepare and execute approved PR proposals |
| reviewer | Accept/decline dossiers; approve/decline exact-file PR proposals |
| admin | All of the above plus connection probes and scoped audit access |

Grants remain paired: stage admin plus production reader does not grant production writes. The example grants no production access. In hosted mode, a PR proposer cannot approve their own proposal. Operator and reviewer permissions may be assigned to distinct groups; both can read their permitted environments.

Sessions are stored in PostgreSQL, capped at the ID token expiry/session lifetime, and use Secure HttpOnly cookies with per-session CSRF protection. Sign-out invalidates the local session; it does not log the person out of their identity provider. There is no token refresh or instant IdP revocation feed; group changes take effect at the next login/expiry.

```dotenv
AABTS_MODE=production
AABTS_PUBLIC_ORIGIN=https://YOUR_WORKSPACE_HOST
AABTS_ALLOWED_HOSTS=YOUR_WORKSPACE_HOST,127.0.0.1
DATABASE_URL=postgresql+psycopg://USER:PASSWORD@HOST:5432/aaaem?sslmode=require
AABTS_OIDC_CLIENT_SECRET=YOUR_SECRET
```

Use a URL-encoded password and your organization's PostgreSQL TLS policy. For certificate verification, configure `sslmode=verify-full` and a trusted database CA available to the container. Use a dedicated application database, backups and restricted networking.

## 7. Enable reviewed file proposals

Configure `environments.<env>.pull_requests` separately from read access:

```json
{
  "repository": "YOUR_ORG/YOUR_PLATFORM_REPO",
  "base_branch": "main",
  "allowed_prefixes": ["docs/agent-reports/", "docs/sites/", "dispatcher/", "conf/sites/"],
  "enabled": true
}
```

The GitHub credential needs repository Contents read/write and Pull requests read/write for that target. Prefer an installation token minted/rotated by your secrets infrastructure or a narrowly scoped token. Automatic GitHub App installation-token minting is not included. Do not give the service merge/admin permissions. Preserve branch protections and repository CI.

Factory templates in `templates/site/manifest.json` are illustrative, incomplete deployment configuration. Replace them with your platform's reviewed vhost, farm, repoinit, i18n and site configuration. Set `templates_directory` to that directory and `templates_approved=true` only after review. The renderer uses validated fields and `${slug}`, `${brand}`, `${market}`, `${locale}`, `${domain}`, `${theme}`, `${environment}` substitutions. The directory must contain `manifest.json` with version 1 and a path-to-content `files` object. Generated paths cannot traverse directories or target hidden files/workflows. Maximum bundle: 30 files / 500,000 characters. The plan describes manual MSM live-copy/provisioning tasks; it never executes AEM writes.

Proposals bind exact files, source result, environment, repository, base branch and base commit to a digest and 24-hour expiry. Approval and execution are separate. Acceptance of an ordinary run dossier does not approve a PR. Interrupted execution reconciles the same deterministic branch/PR; edited trees/parents cannot reuse the approval. If the base branch moves or a proposal expires, create a new run and review a fresh proposal. No tool merges, deploys or publishes.

Reporting/Security generate Markdown files under `docs/agent-reports/`. Approving their PR is how this milestone supplies MkDocs-ready documentation; your documentation repository/pipeline owns navigation, review and publishing.

## 8. Events and schedules

`POST /api/intake` accepts the normalized, signed envelope in INTEGRATION_CONTRACTS.md. A vendor-specific receiver must first verify Adobe/monitoring/Teams authentication, normalize the event, then sign it with `AABTS_INTAKE_SECRET`. This is not a native Teams bot or a direct vendor-webhook signature implementation.

```bash
python scripts/submit_event.py --help
```

The included schedule examples are disabled. After validating a workflow, set `enabled=true`. Schedules use UTC Unix-epoch interval buckets, run once in the current bucket, and do not backfill missed buckets; `1440` minutes aligns to UTC days rather than a chosen local nightly time. The `platform-health` objective runs Security, Governance, Reporting. Reporting summarizes the last 100 runs in its environment, not necessarily an exact calendar week. For precise timezone/calendar schedules, have your enterprise scheduler call the signed intake.

## 9. Acceptance sequence

Start with one stage site and read-only credentials. Check connections, run Release and Incident, inspect the actual evidence, then run a platform-health mission. Validate SSO reader/operator/reviewer boundaries with real tenant accounts. Finally create a draft PR in a controlled repository using reviewed templates, check its diff and repository CI, and only then enable scheduled coverage. Keep live deployment/publishing outside this milestone.

Use docs/IMPLEMENTATION_STATUS.md for remaining product scope and infra/aws/README.md for hosting prerequisites.
