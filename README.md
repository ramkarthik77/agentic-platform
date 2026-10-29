# AABTS Agentic Platform

A standalone operations workspace for the AABTS platform: **one orchestrator and six specialists**, an animated web UI, persisted evidence, environment-scoped access, and governed draft pull requests. It is independent of other applications.

**Version 0.2 is a configuration-ready foundation, not a tenant-certified production system.** All seven roles execute bounded workflows. The default experience uses clearly labeled synthetic data and deterministic summaries; no credentials are required. Live adapters, OIDC, a separate browser verifier, and an AWS deployment starter are included. Your tenant connections and hosting still need configuration and acceptance testing.

## Run locally

Requires Python 3.12 or newer. Node is only needed for the JavaScript syntax check.

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.lock
cp .env.example .env
python scripts/serve.py
```

Open **http://localhost:8000**. On Windows, activate with `.venv\Scripts\Activate.ps1` and use `Copy-Item .env.example .env`. The SQLite database in `.data/aaaem.db` survives restarts. Local mode grants a trusted operator access to all environments; bind it to loopback. The default `production` selection in the UI is a **fixture environment**, not an actual deployment.

Docker with local PostgreSQL is also available:

```bash
docker compose up --build
```

This publishes the application on loopback only. `docker compose down` retains the named database volume.

## What works

| Agent | Implemented behavior | Boundary |
| --- | --- | --- |
| Ops orchestrator | Persistent specialist handoffs, conditional incident investigation, consolidated mission report, cancellation and restart recovery | Four defined mission types; no unrestricted planner |
| Incident & RCA | New Relic metrics, Splunk summaries, deploy correlation, evidence-linked RCA draft | Root cause remains unconfirmed; no arbitrary shell/runbook execution |
| Release & pipeline | Cloud Manager tracking, registry scope, browser checks, revision/freshness validation, review dossier | Does not start deployments or approve Cloud Manager gates |
| Security & quality | Snyk/Sonar triage, quality gate checks, three AEM/Dispatcher heuristics on configured GitHub files, remediation report | Does not generate or test source-code fixes |
| Site factory | Validated site specification, template-rendered files, provisioning plan, ZIP download, approved draft PR | Templates require platform review; no live-copy creation, DNS change or publishing |
| Content governance | Configured-page browser checks, sampled links, SEO/basic accessibility, AEM inheritance bridge results | Bounded checks, not complete WCAG certification or an all-page crawl |
| Reporting & docs | Persisted-history briefs, downloadable Markdown, approval-gated docs PRs | Does not publish MkDocs or send Teams/email notifications |

The UI includes mission control, agent fleet, all specialist run views, site intelligence, review inbox, reports, integration readiness and connection checks. Motion can be paused and respects reduced-motion preferences.

## Try the end-to-end local flow

1. Start a **Team mission** with the **Failures / findings** demo scenario. The orchestrator runs Release, Incident, then Reporting. Inspect the three persisted handoffs and source evidence.
2. Open **Approvals** and accept the release dossier. This records a review; it does not authorize an external action.
3. Run **Site factory**, inspect the six generated files, and download the ZIP.
4. Select **Prepare draft PR proposal**, review the exact file contents, then approve and **Simulate PR creation**. Fixture mode never contacts GitHub.
5. Refresh the browser or restart the application. Runs, files, reports and decisions remain stored.
6. Open **Integrations** to see the configuration and connection-check experience.

## Configure your platform

Start with [the setup guide](docs/SETUP.md). Tenant configuration belongs in ignored files and environment variables, not application code:

- `.env`: runtime mode, database, model selection and secret values/references.
- `config/local.json`: endpoints, environment mappings, OIDC grants, schedules and PR targets.
- `config/registry.local.json`: real site IDs, URLs, page scope and revision headers.
- A reviewed site template directory, if you enable live Site Factory proposals.

Use a **separate database** when switching from fixture to live integrations. Configuration is read at startup. Restart every API/worker instance after changing it.

```bash
python scripts/doctor.py
```

The doctor validates configuration and reports missing variable names without printing secret values. The UI's **Check connection** performs a bounded read probe. A reachable endpoint is not proof that an entire workflow is valid.

Optional narrative providers are Amazon Bedrock Converse and an OpenAI-compatible Chat Completions gateway. `fixture` remains a deterministic text provider and can summarize real evidence without sending it to a model. Models do not select tools, alter deterministic verification assessments, or execute changes.

## AWS hosting

[infra/aws](infra/aws/README.md) contains Terraform for ECS/Fargate API and worker services, an HTTPS load balancer, task roles, secret injection and logs. It uses your existing VPC/subnets, PostgreSQL database, ECR image, certificate, DNS, and Secrets Manager entries. It is **not deployed** by CI.

This release uses the tested PostgreSQL-backed workflow queue. Step Functions, SQS, S3 evidence offload and EventBridge are future migration work, described in [AWS transition](docs/AWS_TRANSITION.md). Do not run a second workflow owner against the same runs.

## Checks

```bash
python -m pytest
python -m compileall -q backend scripts
node --check web/assets/app.js
python -m pip check
```

The PostgreSQL integration test requires `AABTS_TEST_POSTGRES_URL` pointing to a disposable database named `aaaem_test`. Browser tests require Chromium:

```bash
python -m playwright install --with-deps chromium
AABTS_BROWSER_TESTS=1 python -m pytest tests/test_browser.py
```

GitHub Actions runs application tests, PostgreSQL, the connected Chromium UI flow, Terraform validation and container checks. See [validation](docs/VALIDATION.md) for the actual results and unverified boundaries.

## Project map

`web/` contains the UI; `backend/aaaem/` contains the API, persistence, policies, adapters and runtime; `agents/` contains role instructions; `config/` contains examples and JSON schemas; `templates/` contains illustrative Site Factory templates; `tests/` contains behavior tests; `infra/aws/` contains the hosting starter.

- [Setup and endpoint checklist](docs/SETUP.md)
- [Integration contracts](docs/INTEGRATION_CONTRACTS.md)
- [Implementation status and remaining work](docs/IMPLEMENTATION_STATUS.md)
- [AWS deployment starter](infra/aws/README.md)
- [Reference architecture](docs/SOLUTION_DESIGN.md)
