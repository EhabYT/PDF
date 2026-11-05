import sys
import urllib.request

try:
    with urllib.request.urlopen(sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8000/api/health", timeout=5) as response:
        print(response.read().decode())
except Exception as exc:
    print(type(exc).__name__, file=sys.stderr)
    sys.exit(1)
