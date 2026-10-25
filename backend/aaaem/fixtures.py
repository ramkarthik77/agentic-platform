"""Synthetic integration data; never presented as results from live enterprise services."""
from .db import now


def registry():
    regions = ["North America", "Europe", "Asia Pacific", "Latin America"]
    markets = [["US", "CA"], ["DE", "FR", "UK", "IT", "ES", "NL"],
               ["KR", "JP", "AU", "SG"], ["BR", "MX", "CO"]]
    return [{"id": i+1, "name": f"Brand {i//4+1:02}",
             "market": markets[i % 4][(i//4) % len(markets[i % 4])],
             "region": regions[i % 4], "theme": f"Theme {i % 8+1:02}",
             "template": "Core + custom" if i % 3 == 0 else "Standard site",
             "status": "not_checked", "checks": None, "source": "fixture"} for i in range(108)]


def execution(request):
    return {"source": "fixture", "execution_id": "1042", "revision": "a84c2d1",
            "previous_revision": "c91e4ba", "environment": request["environment"],
            "pipeline_status": "completed", "changed_scope": request["scope"],
            "deployment_time": now(-900)}


def impact(request, sites):
    selected = [s["id"] for s in sites if request["scope"] != "theme-04" or s["theme"] == "Theme 04"]
    return {"source": "fixture", "site_ids": selected,
            "reason": "Theme 04 consumers" if request["scope"] == "theme-04" else "Platform-wide baseline",
            "coverage_uncertain": request["scope"] == "unknown"}


def verification(request, selected):
    return {"source": "fixture", "execution_id": "1042", "revision": "a84c2d1",
            "environment": request["environment"], "checks_per_site": 28, "pages_per_site": 4,
            "sites": [{"id": s, "passed": 26 if request["scenario"] == "degraded" and i == 0 else 28,
                       "total": 28} for i, s in enumerate(selected)
                      if not (request["scenario"] == "incomplete" and i == 0)],
            "note": "Fixture results only. No browser checks ran against actual sites."}


def metrics(request):
    return {"source": "fixture", "window_minutes": 30, "requests": 12000,
            "baseline_5xx_rate": 0.002, "current_5xx_rate": 0.04 if request["scenario"] != "healthy" else 0.002,
            "p95_ms": 1100 if request["scenario"] != "healthy" else 250,
            "deployment_overlap": request["scenario"] != "healthy"}


def logs(request):
    return {"source": "fixture", "query": "approved-error-summary", "window_minutes": 30,
            "patterns": [{"pattern": "Upstream timeout on sample content route", "count": 42}]
            if request["scenario"] != "healthy" else [], "redacted": True}
