"""Copy the existing UI into a deployable directory with its WebSocket URL."""
import argparse
from pathlib import Path
import shutil
import json

parser = argparse.ArgumentParser()
parser.add_argument('--websocket-url', required=True)
parser.add_argument('--output', default='dist')
args = parser.parse_args()
if not args.websocket_url.startswith('wss://'):
    parser.error('WebSocket URL must use wss://')
out = Path(args.output)
out.mkdir(parents=True, exist_ok=True)
for path in (Path(__file__).resolve().parents[1] / 'static').iterdir():
    if path.is_file() and path.name != 'config.js':
        shutil.copy2(path, out / path.name)
(out / 'config.js').write_text('window.MUSA_WS_URL = ' + json.dumps(args.websocket_url) + ';\n')
print(out.resolve())
