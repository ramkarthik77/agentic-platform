# Validation record — October 25, 2026

## GitHub Actions — October 25, 2026

The [first repository validation run](https://github.com/ramkarthik77/agentic-platform/actions/runs/40234118073) passed for application commit `e45dd28b1315241e664b1caebf8ef1050cc584f8`.

- 24 automated tests passed, with no skipped tests and one upstream deprecation warning.
- The PostgreSQL integration test passed against the workflow's PostgreSQL 16 service. It was previously skipped locally because no database service was available.
- Dependency installation and consistency, JavaScript syntax, and Python compilation checks passed on the GitHub-hosted runner.
- This workflow validates the application; it does not deploy it.

## Passed in the local build environment — October 23, 2026

- 23 automated tests using SQLite, FastAPI's test client, and the actual local worker implementation.
- API-submitted background execution through persisted evidence and a completed draft.
- Exact-input idempotency, conflicting key rejection and strict request validation.
- Release impact selection: 14 Theme 04 consumers and conservative expansion to 108 sites.
- Missing check coverage and mismatched revisions cannot produce a verified assessment.
- Failed checks remain failed; successful deployment alone is not verification.
- Incident outputs retain unconfirmed root cause.
- Reporting reads stored history and excludes other environments.
- Evidence content hashes and citation references are retained in downloadable reports.
- Review digest/expiry/result binding, duplicate decision replay and conflicting decision rejection.
- Cancelled and expired workers cannot commit later results under an obsolete lease owner.
- Concurrent workers claim a queued run only once; recovery attempts are bounded.
- Provider failures produce a failed run without a completed report; manual retry works.
- Database records and review reasons survive application teardown and restart.
- Read-only tool policy and environment boundaries reject escalation.
- Production mode fails closed until enterprise authentication is implemented.
- A stubbed Bedrock response with fabricated evidence IDs is rejected.
- JavaScript syntax check, Python compilation, and installed dependency consistency check.

## Not execution-verified here

- Docker build/Compose: Docker is not available in the build environment.
- Connected browser UI: the managed preview supervisor could not launch the environment's Python executable. The approved visual prototype had desktop/mobile/tablet checks in the previous milestone, but the newly connected UI has not had a live browser end-to-end pass. JavaScript syntax and backend behavior were checked independently.
- Bedrock model inference: no account/model credentials were used; only the adapter's validation behavior was tested with a stub response.
- Live Cloud Manager, AEM, New Relic, Splunk, GitHub, Teams, Snyk, Sonar or browser scanning: not connected. All enterprise evidence is synthetic.
- AWS resources, SSO/RBAC and Step Functions/SQS dispatch: not deployed.

The test runner emitted one upstream Starlette deprecation warning for the current HTTPX test-client compatibility path; all tests passed. Tests are included in the package and can be rerun after installation.
