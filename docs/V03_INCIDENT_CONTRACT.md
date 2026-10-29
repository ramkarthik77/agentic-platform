# v0.3 Incident Investigation Evidence Contract

This is the proposed contract for the next implementation slice; it does not imply the service is implemented yet.

## Input

```json
{
  "schema_version": "1",
  "objective": "investigate_incident",
  "environment": "stage",
  "site_ids": [101],
  "window": {"start": "2026-10-29T14:00:00Z", "end": "2026-10-29T14:30:00Z"},
  "requested_by": "authenticated_operator"
}
```

Caller identity is derived server-side from the authenticated session, not trusted from the submitted body. Site IDs and environment must be validated against the registry and role grants.

## Evidence item

```json
{
  "id": "ev-001",
  "source": "new_relic",
  "kind": "aggregate_metric",
  "environment": "stage",
  "site_ids": [101],
  "observed_at": "2026-10-29T14:30:00Z",
  "collected_at": "2026-10-29T14:31:00Z",
  "complete": true,
  "safe_summary": "The current 5xx rate exceeded the prior baseline.",
  "source_reference": "opaque-internal-record-id"
}
```

The stored record must track whether evidence is synthetic, truncated, redacted or stale. Never transmit access tokens or unredacted raw logs to the model.

## Investigation output

```json
{
  "schema_version": "1",
  "status": "needs_review",
  "observations": [{"claim": "5xx rate increased", "evidence_ids": ["ev-001"]}],
  "hypotheses": [{"claim": "Deploy-associated regression is possible", "evidence_ids": ["ev-001"], "counterevidence_ids": [], "confidence": "low"}],
  "unknowns": ["No confirmed application root cause"],
  "recommended_human_actions": ["Inspect the deployment delta and error patterns"],
  "prohibited_automatic_actions": ["deploy", "rollback", "publish", "merge"]
}
```

### Enforcement requirements

- Fail schema validation for any observation without a real evidence ID belonging to the run.
- Distinguish failure to collect evidence from evidence proving no incident.
- Label source-specific timestamps and data-window boundaries; compare only compatible metrics.
- A model cannot choose new tools, widen an environment/site scope or approve an action.
- Rendering the dossier must HTML-escape model-supplied claims; avoid raw Markdown/HTML injection.
- Keep a machine-readable decision/audit trail for rejection and fallback.

### Required negative tests

- Invented evidence ID; source environment mismatch; stale release commit; missing revision.
- Truncated NRQL/SPL result; private URL or redirect; credential leakage attempt.
- Model JSON invalid; tool invocation instructions embedded in log summaries; self-approval attempt.
- Duplicate event; expired approval; restarted worker; stage operator attempting production access.
