"""Sign a normalized event. Never prints the shared intake secret."""
import argparse
import hashlib
import hmac
import json
import os
import time
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.parse import urlsplit
from dotenv import load_dotenv
load_dotenv(Path(__file__).resolve().parents[1] / '.env', override=False)
parser = argparse.ArgumentParser()
parser.add_argument('--url', required=True)
parser.add_argument('--file', required=True)
args = parser.parse_args()
if urlsplit(args.url).scheme != 'https' and urlsplit(args.url).hostname not in {'127.0.0.1', 'localhost'}:
    parser.error('Use HTTPS, or a loopback URL for local testing')
key = os.environ.get('AAAEM_INTAKE_SECRET', '')
if len(key) < 32: parser.error('Set AAAEM_INTAKE_SECRET to at least 32 random characters')
body = json.dumps(json.loads(Path(args.file).read_text()), separators=(',', ':')).encode()
timestamp = str(int(time.time()))
signature = hmac.new(key.encode(), timestamp.encode() + b'.' + body, hashlib.sha256).hexdigest()
request = Request(args.url.rstrip('/') + '/api/intake', data=body, headers={'Content-Type': 'application/json',
    'X-AAAEM-Timestamp': timestamp, 'X-AAAEM-Signature': signature})
with urlopen(request, timeout=20) as response:
    print(response.read().decode())
