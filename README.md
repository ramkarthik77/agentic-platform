# AAAEM Agentic Platform

Repository: [ramkarthik77/agentic-platform](https://github.com/ramkarthik77/agentic-platform).

The approved AAAEM interface, connected to a standalone local backend. This is the first implementation milestone: persistent runs, a database-backed queue, scoped evidence collection, draft review, and reports for the Incident, Release, and Reporting agents.

**Integration data is synthetic.** The default model provider is deterministic fixture mode. No AWS account, AI API, or enterprise credentials are needed to exercise the application.

## Run locally

Use Python 3.12 or newer. Clone the repository, then run on macOS/Linux:

```bash
git clone https://github.com/ramkarthik77/agentic-platform.git
cd agentic-platform
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.lock
python scripts/serve.py
```

Open **http://localhost:8000**. Keep the terminal running. Stop with Ctrl+C. Restarting the same command retains runs and decisions in `.data/aaaem.db`.

On Windows, create the venv with `py -3.12 -m venv .venv`, then use `.venv\Scripts\python.exe` in place of `python` in the install and serve commands.

The HTML now requires the backend; opening `web/index.html` directly is not supported. Node is optional and only used for the JavaScript syntax check and the `npm run dev` convenience command after activating the Python environment.

## Try the full workflow

1. Click **Start an agent run** and choose **Release verification**.
2. Keep **Theme 04 consumers** selected. The backend selects 14 of the 108 registered fixture sites.
3. Watch the activity stream, then inspect the run's timeline and expandable evidence records.
4. Open **Approvals**, review the dossier, and accept or decline the draft. A decision acknowledges the dossier only; it cannot deploy, publish, or approve a Cloud Manager gate.
5. Open **Reports** and download the generated Markdown dossier.
6. Refresh the browser or restart the server. The run, evidence, report, and review decision remain.
7. Try **Failed checks**, **Missing verification evidence**, and **Unknown dependencies**. Missing or revision-mismatched evidence results in an inconclusive assessment; unknown dependency scope expands to all fixture sites.
8. Run **Incident investigation**, then **Platform brief** to summarize persisted activity in the selected environment.

The environment picker filters the workspace and scopes new work. Choosing “production” is still a fixture-only read workflow.

## Implemented boundaries

| Area | Current behavior |
| --- | --- |
| UI | Original constellation, motion controls, accents, agent fleet, releases, incidents, registry, reviews, reports and integration status |
| Ops dispatcher | Routes three explicit workflow kinds; bounded queue, claim leases, cancellation, manual retry and restart recovery |
| Release | Revision-bound fixture verification, dependency scope, missing/failing evidence handling, review dossier |
| Incident | Bounded fixture telemetry/logs, deployment correlation, unconfirmed RCA draft |
| Reporting | Summary of up to 100 persisted runs in the selected environment; no external publishing |
| Persistence | SQLite by default; SQLAlchemy PostgreSQL adapter and optional integration test |
| Tools | Server-created execution context; read allowlists by role and environment; no write executor |
| Review | Exact payload/result hashes, 24-hour expiry, atomic decision, idempotent replay, retained reason |
| Model | Fixture provider by default; opt-in Bedrock Converse adapter with validated output and known evidence IDs |
| Other agents | Security, Site Factory, and Governance remain explicitly planned |

The local queue is the development runtime. The production design still assigns durable execution to Step Functions Standard, queue transport to SQS, compute to ECS/Fargate, application data to RDS, and evidence blobs to S3. See [AWS transition](docs/AWS_TRANSITION.md).

## Optional model-backed summaries

After your organization approves the model, configure AWS credentials through a normal AWS profile and export:

```bash
export AAAEM_MODEL_PROVIDER=bedrock
export AAAEM_BEDROCK_MODEL_ID='your-approved-model-or-inference-profile-id'
export AWS_REGION=us-east-1
export AWS_PROFILE='your-local-profile'
python scripts/serve.py
```

This enables real, billable model requests. Enterprise integrations remain fixtures. The model summarizes evidence; it does not choose arbitrary tools or execute changes. Invalid JSON or unknown evidence citations fail the run. The deterministic verification assessment is separate from model prose. Bedrock was not contacted during validation.

`.env.example` documents settings; the server reads process environment variables and does not automatically load a `.env` file.

## Optional Docker + PostgreSQL

```bash
docker compose up --build
```

Open http://localhost:8000. Named volumes preserve the database. `docker compose down` stops services while retaining volumes. The application port is published only on loopback. Docker was unavailable in the build environment, so this path is provided but not execution-verified here.

## Checks

```bash
python -m pytest
node --check web/assets/app.js
python -m compileall -q backend scripts
```

The PostgreSQL smoke test is opt-in via `AAAEM_TEST_POSTGRES_URL`; it requires a dedicated disposable database named `aaaem_test` and resets its tables. CI configures that database. See [validation](docs/VALIDATION.md) for the checks actually run and remaining limits.

## API and code map

- `GET /api/bootstrap` — initial registry, role catalog, records and local CSRF token.
- `GET /api/workspace` — latest 100 runs/reviews/reports and recent events.
- `POST /api/runs` — validated input plus `Idempotency-Key` and `X-AAAEM-CSRF` headers.
- `GET /api/runs/{id}` — timeline, result and evidence ledger.
- `POST /api/runs/{id}/cancel` or `/retry` — governed local lifecycle controls.
- `POST /api/approvals/{id}/decision` — exact digest plus approved/declined draft decision.
- `GET /api/reports/{id}?download=true` — stored Markdown artifact.
- `GET /api/audit` — recent local audit records.
- `GET /api/openapi.json` — machine-readable API schema.

`web/` owns the UI. `backend/aaaem/` owns contracts, persistence, tool policy, model providers, API and workers. `agents/` owns the seven-role catalog and Phase 1 instructions. `tests/` exercises behavior at API and workflow boundaries.

## Hosting boundary

This milestone is for a trusted local operator. CSRF and host checks are not enterprise authentication. The application refuses `AAAEM_MODE=production`. Keep the local bind address and Docker loopback port binding; do not expose it publicly. Enterprise SSO/RBAC, real adapters, webhook verification, cloud workflow dispatch, and deployment verification are the next milestones. The repository includes validation CI only; it does not deploy the app or create AWS infrastructure.
