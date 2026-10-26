# Implementation status — 0.2

This is a runnable seven-role foundation with configurable integrations. It is **not the complete autonomous platform described in the original reference architecture**. Endpoint configuration is the next handoff for standard adapters; some organization-specific services and later product capabilities still require implementation.

## Delivered in this repository

- Animated responsive dashboard, agent fleet, missions, specialist run histories, site intelligence, review inbox, reports and connection readiness/probes.
- Seven executable roles with explicit tool allowlists; four mission plans with persisted specialist handoffs and evidence-linked summaries.
- SQLite local mode and PostgreSQL path; transactional run/evidence/report/review storage, idempotency, claims, leases, restart recovery, cancellation, retries and audit records.
- Native read adapters for Cloud Manager, New Relic, Splunk, Snyk, Sonar and configured GitHub file review; an authenticated bridge client for AEM/tenant metadata.
- Separate Playwright verification service with bounded page/link/SEO/basic accessibility checks and measured served-revision headers.
- Strict site registry/configuration schemas, no fixture fallback in live mode, missing-connection evidence, conservative impact scope, incomplete/freshness checks.
- OIDC code + PKCE, RS256 validation, database sessions, CSRF, group/role/environment grants, separate reviewer identity for hosted PR approval.
- Deterministic site template renderer, ZIP exports and provisioning plans. Site Factory, Security and Reporting can propose supported file bundles as draft GitHub PRs.
- Exact-file/base-revision approval, expiry, separate execution and reconciliation after interrupted PR creation. No merge/deploy/publish capability.
- Signed normalized intake, interval schedules, optional Bedrock/compatible-gateway narration, safe configuration doctor and setup guide.
- Docker/Compose definitions, separate worker entry point, ECS/Fargate Terraform starter, CI and behavior tests.

## You configure

Your site registry; stage/production endpoint mappings; scoped credentials; Adobe IDs/OAuth settings; reviewed monitoring queries; Snyk/Sonar projects; GitHub target/path permissions; OIDC tenant/groups; approved model ID if used; schedule choices; and reviewed site templates. AWS also needs networking, PostgreSQL, an image registry/digest, certificate, DNS and secret entries.

## Additional implementation or tenant work still needed

| Capability | Current boundary / remaining work |
| --- | --- |
| Real AEM inheritance inspection | Supply an AEM bridge that reads your supported MSM metadata and exceptions; only its client/contract are included |
| Reliable release revision metadata | Configure an actual served-revision header and validate Cloud Manager commit metadata; if native execution output lacks it, supply a reviewed build-metadata bridge |
| Security source-code fixes | Current output is triage/remediation Markdown; implementing/testing source patches and PR-diff review remain future work |
| Site provisioning | Generated files and a plan only; repository-specific validation, MSM live copies, DNS/certificates, content writes and publishing remain outside the app |
| Native Teams/vendor events | Supply a receiver that verifies original vendor identities and signs normalized events; bot commands, Adaptive Cards and notifications remain future work |
| Full release automation | No pipeline start, Cloud Manager gate approval, deployment, rollback or automatic release-note changelog extraction |
| MkDocs synchronization | Report Markdown can be delivered as an approved draft PR; navigation, merge and publication remain with your docs pipeline |
| Comprehensive site quality | No full WCAG audit, authenticated business journeys, recursive link crawl, visual regression baseline or evidence screenshot archive |
| AWS reference architecture | Terraform uses PostgreSQL workflow ownership; Step Functions, SQS/DLQ, S3 evidence storage and EventBridge migration are not implemented |
| Operations at scale | Load/soak testing, alarms, rate limits at ingress, retention/archive jobs, backup-restore drills, secret rotation automation and tenant security review remain rollout tasks |

The default UI shows the latest 100 runs/reports and bounded audit history. Older records remain in the database but there is no complete searchable archive or retention job. A weekly interval report uses the last 100 environment runs, not a strict calendar-week query. The registry supports 1,000 sites and each verification run is capped at 250 sites; size schedules and workers accordingly.

The role catalog represents a team of cooperating bounded workflows. Optional models write structured narrative from evidence; they do not independently plan arbitrary tasks or operate tools. This boundary is intentional and visible in the UI/configuration.

See VALIDATION.md for exactly what has been executed. A green test suite is not proof of tenant integration or production readiness.
