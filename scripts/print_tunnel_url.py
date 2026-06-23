"""Poll tunnel.log for the public trycloudflare.com URL, print + save it.

Called by start.bat after launching cloudflared. cloudflared prints the quick
tunnel URL to its log; we wait up to ~30s for it to appear.
"""
from __future__ import annotations

import re
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LOG = ROOT / "tunnel.log"
OUT = ROOT / "tunnel-url.txt"

URL_RE = re.compile(r"https://[a-z0-9-]+\.trycloudflare\.com")


def main() -> None:
    deadline = time.time() + 30
    url = None
    while time.time() < deadline:
        if LOG.exists():
            text = LOG.read_text(encoding="utf-8", errors="ignore")
            m = URL_RE.search(text)
            if m:
                url = m.group(0)
                break
        time.sleep(0.5)

    if url:
        OUT.write_text(url + "\n", encoding="utf-8")
        print()
        print("===========================================================")
        print(f"  REMOTE ADMIN URL:  {url}")
        print(f"  (open {url}/admin  or  {url}/reports )")
        print("===========================================================")
    else:
        print("[tunnel] Could not detect the public URL yet.")
        print("[tunnel] Check tunnel.log; the URL may appear there shortly.")


if __name__ == "__main__":
    main()
