"""Container probe: degraded service remains usable and passes the probe."""
import os
import sys
import urllib.request


def main():
    try:
        with urllib.request.urlopen(f'http://127.0.0.1:{os.environ.get("PORT", "1876")}/health', timeout=5) as response:
            return 0 if response.status == 200 else 1
    except Exception:
        return 1


if __name__ == '__main__':
    sys.exit(main())
