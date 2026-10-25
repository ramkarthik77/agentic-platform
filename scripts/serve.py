"""Run the standalone local workspace; bind only to loopback unless explicitly overridden."""
import argparse
import sys
from pathlib import Path

root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root / "backend"))
parser = argparse.ArgumentParser()
parser.add_argument("--host", default="127.0.0.1")
parser.add_argument("--port", default=8000, type=int)
args = parser.parse_args()

import uvicorn
from aaaem.api import create_app
uvicorn.run(create_app(), host=args.host, port=args.port)
