"""Dedicated queue worker for PostgreSQL deployments; no HTTP listener."""
import signal
import sys
from pathlib import Path
root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root / 'backend'))
from dotenv import load_dotenv
load_dotenv(root / '.env', override=False)
from aaaem.runtime import prepare_config
prepare_config()
from aaaem import db, fixtures
from aaaem.config import Settings
from aaaem.setup import read_registry
from aaaem.service import Platform

settings = Settings()
settings.validate()
engine = db.make_engine(settings.database_url)
registry = fixtures.registry() if settings.integration_mode == 'fixture' else read_registry(settings.workspace)
db.initialize(engine, registry, settings.integration_mode)
platform = Platform(engine, settings)
for event in (signal.SIGTERM, signal.SIGINT):
    signal.signal(event, lambda *_: platform.stop_event.set())
try:
    platform.loop()
finally:
    engine.dispose()
