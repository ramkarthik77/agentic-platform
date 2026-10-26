"""Run behind an HTTPS proxy, or provide a local certificate and key explicitly."""
import argparse
import sys
from pathlib import Path
root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root / 'backend'))
from dotenv import load_dotenv
load_dotenv(root / '.env', override=False)
parser = argparse.ArgumentParser()
parser.add_argument('--host', default='127.0.0.1')
parser.add_argument('--port', default=9000, type=int)
parser.add_argument('--ssl-certfile')
parser.add_argument('--ssl-keyfile')
args = parser.parse_args()
import uvicorn
from aaaem.verifier import create_verifier
uvicorn.run(create_verifier(), **vars(args))
