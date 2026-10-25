# AWS implementation sequence

The application is a standalone AAAEM system with its own codebase, runtime and deployment lifecycle.

## Current development runtime

FastAPI serves the approved web UI and API. A local worker claims persisted runs using compare-and-update ownership, bounded attempts, and expiring leases. Evidence, reports, reviews, and audit records are committed transactionally. SQLite is the default; a SQLAlchemy PostgreSQL path is included. Inputs use fixture adapters. Bedrock inference is optional.

The local worker is deliberately a development adapter. Do not run it in parallel with Step Functions as competing workflow owners.

## Milestone 2 — enterprise identity and first live read adapter

1. Use the dedicated [ramkarthik77/agentic-platform](https://github.com/ramkarthik77/agentic-platform) repository. Establish the AWS account/region, VPC and enterprise identity integration.
2. Add OIDC session validation, role/group mapping, per-environment/site authorization and a real reviewer identity. Remove the local principal from the enterprise configuration.
3. Implement Cloud Manager read access for allowlisted programs/pipelines, OAuth credential handling, bounded API calls and error handling. Keep live integration mode explicit and independently configurable from the model provider.
4. Map the real site registry and dependency owners. Do not promote fixture site IDs or health values into production data.
5. Test one non-production pipeline and validate execution/revision binding against native Cloud Manager records.

## Milestone 3 — AWS workflows and observability

1. Provision reviewed ECR, ECS/Fargate, RDS PostgreSQL, S3, Secrets Manager, IAM and log configuration. Pin deployment images by digest and establish controlled egress and backups.
2. Replace the embedded local worker with a dispatcher/outbox and Step Functions Standard. Keep the case and review API contracts; persist workflow execution IDs and reconcile workflow state into application records.
3. Authenticate and deduplicate provider webhooks before durable intake. Use SQS with defined visibility, retry ownership and dead-letter handling.
4. Store evidence blobs in restricted S3 objects, retaining hashes, provenance, retention policy and metadata in RDS.
5. Add New Relic and Splunk adapters with bounded queries, redaction and scope enforcement. Reuse one verification service for release and governance checks.
6. Add real Playwright results with revision, environment, affected-site scope, selected journeys and retained artifacts. Never treat fixture pass values as execution evidence.
7. Add EventBridge scheduling only after workflow idempotency, budgets, alerting and operational ownership are verified.

## Milestone 4 — controlled action capabilities

Add Security & quality, Site Factory and Governance remediation incrementally. PR creation, merges, deployments, content writes, publication and messaging require separate tool contracts and approved policies. Review acceptance in this build authorizes none of these operations. Keep the requesting agent unable to approve its own proposed action.

## Decisions still required for deployment

- Enterprise CI identity and repository access policy; the source repository is `ramkarthik77/agentic-platform`.
- AWS account, region, approved VPC/ingress and outbound paths.
- Enterprise SSO/group-to-role mapping and audit retention.
- Approved model endpoint, model ID, classification and data-retention policy.
- Read scopes and credential owners for Cloud Manager, AEM, New Relic and Splunk.

These do not block local development. No fabricated ARNs, account IDs, secret values or deployment targets are included.

## Implementation references

- [FastAPI lifespan](https://fastapi.tiangolo.com/advanced/events/)
- [SQLAlchemy SQLite](https://docs.sqlalchemy.org/en/20/dialects/sqlite.html)
- [SQLAlchemy transactions](https://docs.sqlalchemy.org/en/20/tutorial/dbapi_transactions.html)
- [Bedrock Converse SDK contract](https://docs.aws.amazon.com/boto3/latest/reference/services/bedrock-runtime/client/converse.html)
