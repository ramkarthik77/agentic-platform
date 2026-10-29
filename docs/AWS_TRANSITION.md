# AWS runtime and later migration

## Current implementation — version 0.2

The application now has seven bounded roles, persisted specialist handoffs, live-source adapter configuration, OIDC sessions and scoped access, normalized signed intake, exact-file draft PR approvals, interval schedules and a separate browser verifier. The same database-backed workflow engine runs locally or as a dedicated worker process. SQLite is for local development; the hosted path requires PostgreSQL.

The Terraform starter in `infra/aws/` hosts API and worker services on ECS/Fargate with a configured existing PostgreSQL database, secret injection, HTTPS load balancing and logs. It does not deploy automatically, and it has not been applied to an AWS account. Existing network, database, image registry, certificate, DNS, tenant metadata bridge and verification endpoint must be supplied.

This is an explicit implementation change from the original target architecture: **PostgreSQL leases currently own workflow execution. Step Functions and SQS are not implemented.** Keeping one tested owner avoids two services retrying or advancing the same run independently.

## Why keep this runtime for the first hosted pilot

Each workflow has a bounded set of read tools, a small number of persisted handoffs, and separate review/action records. Worker ownership is claimed transactionally and renewed before bounded steps/batches. Interrupted leases are recovered with a maximum attempt count; cancelled or superseded owners cannot commit late results. Reviews do not hold a worker open. PR execution uses a separate claim and deterministic branch identity to reconcile an unknown result.

This is not a promise of unlimited scale or exactly-once remote effects. Load-test the actual site estate, quotas, database, provider latencies and concurrent workers. The code bounds active submissions and site batches, but it does not provide a distributed global provider rate limiter or a DLQ. External events are authenticated/deduplicated directly into persisted run records.

## Future Step Functions/SQS migration

1. Add a transactional event outbox and a single dispatcher. Persist the remote workflow execution ARN alongside the run before enabling new ownership.
2. Introduce Step Functions Standard for durable sequencing, retry ownership and approval callbacks, with versioned input contracts and idempotent activity handlers.
3. Use SQS for transport, visibility and DLQ/replay operations. Define which component owns each retry; do not let the old worker claim externally owned runs.
4. Move large evidence artifacts to restricted S3 storage, retaining content hashes, metadata and access decisions in PostgreSQL.
5. Use EventBridge for precise calendar/timezone schedules. Preserve the same intake authorization and idempotency contracts.
6. Isolate approved write execution and scan/build workloads into separate task roles, credentials and egress boundaries. The current PR executor is separate application logic but still runs in the API process.
7. Add reconciliation, rollback/migration tests, rate budgets, retention and backup-restore drills before migrating production cases.

The reference solution design remains the longer-term architecture, not a list of deployed services. Keep these boundaries visible in status and rollout documentation.
