# AWS deployment starter

This module prepares the **current PostgreSQL-backed runtime** on ECS/Fargate. It creates an ECS cluster, separate API/worker services, task definitions/roles, CloudWatch log group, private task security group, HTTPS Application Load Balancer and database ingress rule. It does not deploy itself from GitHub Actions. No AWS resources have been created during development.

## Required existing resources

| Input | Provide |
| --- | --- |
| Network | VPC, two private task subnets across AZs, two ALB subnets, VPN/operator CIDRs, NAT or approved egress for vendor APIs |
| Database | Dedicated RDS PostgreSQL database/user, database security group, TLS configuration, backups and connection URL |
| Image | Main application image in ECR, pinned by SHA-256 digest |
| HTTPS | Validated ACM certificate in the ALB region; DNS hostname you will point to the ALB |
| Secrets | Workspace JSON, registry JSON, database URL, OIDC client secret and required integration credentials in Secrets Manager |
| Identity | OIDC app/client, callback URL, ID-token group claim and scoped grants |
| Optional inference | Approved Bedrock model/profile and all necessary model/profile ARNs, or compatible-gateway settings |
| Verification / AEM | Separately hosted HTTPS verification service and tenant metadata bridge |

The ALB is internal by default. The module does not create the VPC, NAT, RDS, ECR repository, ACM certificate, DNS record, verifier service, AEM bridge, WAF, CloudWatch alarms, remote Terraform backend, or S3 evidence archive. Those remain explicit prerequisites/rollout work. It targets the commercial AWS partition. Default task egress permits outbound access; narrow it through your VPC egress controls. Do not run the public-site browser scanner in the API/worker task or grant it internal network access.

## Build and stage the image

Build the repository's main Dockerfile for Linux AMD64 and push it to your approved ECR repository using your existing CI/cloud workflow. Resolve its immutable digest for `image_uri`. Reviewed Site Factory templates must be included in that image at a configured path; the bundled examples are not production templates. Build `Dockerfile.verifier` separately if you operate the included scanner.

The main image runs as UID 10001. The API service disables its embedded worker. The dedicated worker service runs `scripts/worker.py`; work survives task replacement through database leases. The API health endpoint probes the database; the worker health check observes its heartbeat. Start at one API and one worker, then load-test before scaling. Both services use identical configuration and database schema.

## Secret injection

The `secret_arns` map contains **ARN references**, never secret values:

- `DATABASE_URL`: full SQLAlchemy PostgreSQL connection URL with your TLS settings.
- `AAAEM_WORKSPACE_JSON`: contents of your reviewed workspace JSON.
- `AAAEM_REGISTRY_JSON`: contents of the real registry JSON.
- `AAAEM_OIDC_CLIENT_SECRET`, plus each variable referenced by connection configuration.

ECS injects these as environment variables. `prepare_config()` materializes configuration/registry into mode-0600 files in a mode-0700 temporary directory and removes the two large JSON variables from the application environment. Credentials remain runtime environment values and are never exposed by the setup endpoint. Restart tasks after changing secrets/configuration; existing containers do not automatically refresh injected values. If secrets use customer-managed KMS keys, supply `secret_kms_key_arns` and ensure the key policy permits the execution role.

The execution role can read only the supplied secret resources. The task role has no AWS write policy; an optional Bedrock policy allows invocation of configured resources. GitHub draft PR writes use your separately scoped GitHub credential. Put no merge/deploy/admin credentials in this service.

## Review and apply in your AWS account

```bash
cp terraform.tfvars.example terraform.tfvars
# Fill in every placeholder and configure your organization's remote state backend.
terraform init
terraform fmt -check
terraform validate
terraform plan -out=aaaem.plan
# Review the plan in your deployment process, then apply the reviewed plan.
terraform apply aaaem.plan
```

The module includes a provider lock file. Keep state and saved plans out of source control; they may contain sensitive infrastructure metadata. Configure encrypted remote state/locking before shared use. Never import or repurpose another application's state.

After creation, use the output ALB DNS name/zone ID for your DNS alias and confirm the certificate covers `hostname`. The OIDC callback is `https://<hostname>/auth/callback`. The app uses the explicit public origin for auth/CSRF rather than trusting arbitrary forwarded headers.

Enable RDS backups/PITR and validate a restore. Record CloudWatch alarms for unhealthy services, repeated workflow failure and backlog growth. Add your perimeter request-rate policy and log retention. Start with read-only stage connections, verify environment/role boundaries, and execute a controlled draft PR before production access or schedules.

## Migration and rollback

Version 2 adds tables to the previous schema without deleting run/evidence records. PostgreSQL startup takes a transaction-level advisory lock to serialize schema/registry initialization across API/worker replicas. Use identical configuration during rollout and take a backup before upgrading. Do not run older and newer schema owners for an extended period; the old version refuses schema version 2. Rollback requires a compatible image or a reviewed database restore, not a blind downgrade.

ECS deployment circuit breakers are enabled. A healthy container does not certify vendor access or complete workflow behavior. The Terraform module has been designed for validation without cloud credentials; an account-specific `plan`, actual provisioning and tenant acceptance remain required.

## Design boundary

This is deliberately the same workflow implementation tested locally and against PostgreSQL. Step Functions/SQS are not additional execution owners. See ../../docs/AWS_TRANSITION.md for the future outbox/dispatch migration.

Primary references:

- https://docs.aws.amazon.com/AmazonECS/latest/developerguide/secrets-envvar-secrets-manager.html
- https://docs.aws.amazon.com/AmazonECS/latest/developerguide/specifying-sensitive-data.html
- https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/ecs_service
