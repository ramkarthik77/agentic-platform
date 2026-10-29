"""Validate configuration and print missing variable names; never print secret values."""
import json
import sys
from pathlib import Path
root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root / 'backend'))
from dotenv import load_dotenv
load_dotenv(root / '.env', override=False)
from aaaem.config import Settings
from aaaem.runtime import prepare_config
from aaaem.connections import Connections
from aaaem.setup import read_registry
try:
    prepare_config()
    settings = Settings()
    settings.validate()
    sites = read_registry(settings.workspace) if settings.integration_mode == 'live' else []
    connections = Connections(settings)
    print(json.dumps({'valid': True, 'mode': settings.mode, 'inputs': settings.integration_mode,
        'model_provider': settings.provider, 'configured_registry_sites': len(sites),
        'environments': {e: connections.readiness(e) for e in ['dev', 'stage', 'production']}}, indent=2))
except Exception as exc:
    print(json.dumps({'valid': False, 'error_type': type(exc).__name__,
                      'message': 'Configuration validation failed. Check config/workspace.schema.json and docs/SETUP.md.'}))
    raise SystemExit(1)
