# Validation record — October 26, 2026

## Version 0.2 local checks

- 70 automated tests passed; two integration tests were skipped locally because PostgreSQL and the browser-test runtime were not enabled. One upstream Starlette HTTPX test-client deprecation warning remains.
- All seven workflow types, conditional persisted handoffs, restart recovery, cancellation, idempotent schedules and signed intake were exercised.
- Tests cover role/environment isolation, exact-file PR approval/expiry, OIDC signature/issuer/audience/nonce/authorized-party validation, PKCE callback consumption, session creation and logout.
- HTTP MockTransport tests exercise native adapters and complete live-mode release handling without real credentials. Missing served-revision proof cannot yield `verified`. Wrong environment/fixture bridge responses, redirects, response limits and truncated pagination are rejected or marked incomplete.
- Mock GitHub tests verify draft-only PR creation, reconciliation after a lost response, changed-base rejection and rejection of edited tree/parent commits under an existing approval.
- JavaScript syntax, Python compilation and installed dependency consistency passed.
- Terraform formatting passed and the provider lock was generated. Local schema validation could not start the AWS provider plugin in this execution environment; CI performs validation on a clean runner.

## CI verification

The version 0.2 workflow is configured to run PostgreSQL 16 integration, a real Chromium UI flow, Terraform validation, application container startup and verifier-container Chromium launch. The pull request's checks are the authoritative result; configured checks are not claimed as passed until their run completes.

The UI test launches a mission, inspects specialist handoffs, accepts a dossier, creates/downloads a site bundle, separately approves/simulates its PR, checks persistence after refresh, probes an integration, and checks a mobile layout. Screenshots are retained as the `browser-evidence` CI artifact.

## Environment limitation

The managed local browser preview could not launch `.venv/bin/python`: its interpreter target is unavailable in the preview supervisor's environment. Connected local browser QA remains unverified here. The earlier approved visual prototype had desktop/tablet/mobile checks; that is separate from the connected version 0.2 browser flow.

## Not tenant-validated or deployed

No actual Cloud Manager, New Relic, Splunk, Snyk, Sonar, AEM metadata bridge, tenant OIDC session, GitHub target-repository PR action, Bedrock/compatible-model inference, or public-site scan was performed. Integration tests use controlled HTTP doubles or fixture data. There has been no AWS plan/apply, deployment, load test, security certification or backup-restore drill.

Step Functions/SQS, native Teams/vendor receivers, AEM provisioning, source-code auto-fixes and automatic publishing are not implemented; see IMPLEMENTATION_STATUS.md.

## Previous baseline

The [Phase 1 repository run](https://github.com/ramkarthik77/agentic-platform/actions/runs/40234118073) passed 24 tests, including PostgreSQL, for commit `e45dd28b1315241e664b1caebf8ef1050cc584f8`. That validates the earlier three-role milestone, not all changes in version 0.2.
