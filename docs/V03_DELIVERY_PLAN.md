# AABTS Agentic Platform v0.3 — Integration & Intelligent Orchestration

**Status:** Phase 1 implementation branch. Existing v0.2 behavior is intentionally preserved.
**Product branding:** AABTS. The existing `AAAEM_*` environment variables, database identifiers, Python package names, and API contracts are retained temporarily for compatibility. Rename only with explicit migrations and tests.

## Product outcome

An engineer selects a stage environment and starts an incident investigation. The platform gathers scoped, real read-only release, New Relic, and Splunk evidence, distinguishes observations from hypotheses, records agent handoffs, optionally generates a citation-bound analysis through an approved model, and delivers a reviewable incident dossier. No production mutation, deployment, rollback, or PR merge is performed.

## Delivery gates

### Gate A — Reproducible local baseline
- [ ] Docker Compose starts UI, API, worker and PostgreSQL with health checks.
- [ ] Fixture mode completes the incident/release/reporting mission, persists handoffs across restart, and clearly labels synthetic evidence.
- [ ] Automated Python, browser, PostgreSQL, and container checks pass on the feature branch.
- [ ] No fixtures or credentials are mixed into the live database.

### Gate B — Real read-only stage integration
- [ ] One approved stage environment and site registry are configured.
- [ ] Cloud Manager execution identity, environment and exact commit are validated.
- [ ] New Relic retrieves bounded aggregate NRQL evidence with a defined window and non-sensitive output.
- [ ] Splunk retrieves bounded, aggregated SPL summaries, not raw logs.
- [ ] Missing credentials, timeouts, truncation, stale data and environment mismatch produce **incomplete/inconclusive**, never synthetic success.
- [ ] Every observation records source, timestamps, environment, site scope and evidence reference.

### Gate C — Agent reasoning (governed)
- [ ] Deterministic collection and policy gateway remain in control of tools and scope.
- [ ] Optional approved-model output uses a versioned schema: facts with evidence IDs, hypotheses, alternate explanations, confidence rationale, unknowns, recommended next *human* actions.
- [ ] Reject fabricated evidence IDs, ungrounded facts, unsupported severity claims, and output requesting unauthorized execution.
- [ ] Record model/provider/version, prompt template version, input evidence references, token/cost budget, and validation outcome without storing secrets.
- [ ] If the model fails, show the deterministic incident dossier, not a blank result or an invented conclusion.

### Gate D — Security & enterprise acceptance
- [ ] Verify OIDC login, logout, CSRF, reviewer/operator separation and environment grants against real non-production identities.
- [ ] Confirm per-agent/tool allowlists and deny-by-default behavior for unavailable integrations.
- [ ] Redact source data before inference and prohibit credentials, personal data, and unapproved raw logs in prompts.
- [ ] Test SSRF controls, redirect rejection, request budgets and egress isolation for the browser worker.
- [ ] Confirm no deploy/merge/publish/rollback paths are reachable from agent-generated content.
- [ ] Demonstrate cancellation, retries, duplicate-event handling, audit traceability and failure recovery.

## First demo — required evidence

1. Operator starts **Investigate stage incident** against a registered site or explicit stage scope.
2. Ops Orchestrator assigns Release then Incident then Reporting with persisted handoffs.
3. Evidence view shows actual Cloud Manager execution/revision, bounded New Relic aggregates and Splunk patterns (with source/time/scope).
4. Investigation separates **observed**, **hypothesized**, and **unknown**; missing integrations are explicit.
5. Reviewer can accept a dossier without triggering a system mutation.
6. The run can be refreshed, retried and audited; each external action stays read-only.

## Out of scope for v0.3 first increment

Autonomous production actions; unrestricted agent planning; native Teams bot; real AEM author writes; automatic security patching; arbitrary shell tools; provisioning/publishing; Step Functions/SQS migration; full WCAG certification.

## Technical sequence

1. Preserve v0.2 compatibility and add AABTS product branding.
2. Define incident evidence/output schemas and negative test cases.
3. Add bounded staged live integration test fixtures and contract tests.
4. Add validated optional model synthesis with explicit evidence references.
5. Instrument handoffs, redaction, completeness, budgets, traces and evaluation outcomes.
6. Run stage tenant acceptance, then prepare AWS deployment/security review.

**Release rule:** Do not label v0.3 enterprise-ready until Gates A–D pass with documented evidence. Test doubles do not count as tenant validation.
