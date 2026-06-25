"""Download the latest code from the public GitHub repo and apply it.

Used by update.bat to update the kiosk WITHOUT git installed: it downloads the
repo's branch ZIP, extracts it, and copies code files over the current install
while PRESERVING local data and secrets (.env, lunch.db, backups/, ngrok.exe).

Stdlib only. Safe to run repeatedly.

Config (edit these or pass via env):
  GITHUB_REPO   e.g. "yourname/lunchFMG"     (required)
  GITHUB_BRANCH e.g. "main"                  (default: main)

What it copies:  app/, scripts/, static/, tests/, *.py, *.bat, requirements.txt,
                 README.md, .env.example
What it NEVER touches:  .env, *.db / *.db-*, backups/, .venv/, ngrok.exe,
                        tests/data/real_cards.xlsx, *.log, tunnel-url.txt
"""
from __future__ import annotations

import io
import os
import shutil
import ssl
import sys
import urllib.request
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# ---- repo config: EDIT THESE (or set the env vars in update.bat) ------------
GITHUB_REPO = os.environ.get("GITHUB_REPO", "SabaZara/lunchFMG").strip()
GITHUB_BRANCH = os.environ.get("GITHUB_BRANCH", "main").strip()

# Directories copied wholesale (their contents replace the local ones).
COPY_DIRS = ["app", "scripts", "static"]
# tests/ is copied EXCEPT tests/data (which holds the gitignored real cards).
COPY_TESTS_CODE = True
# Individual top-level files copied if present in the download.
COPY_FILES = [
    "run.py", "tunnel_proxy.py", "requirements.txt", "README.md", ".env.example",
    "start.bat", "quick-start.bat", "kiosk.bat", "kiosk-test.bat",
    "stop.bat", "diagnose.bat", "update.bat",
]

# Never overwrite / never delete these (local data + secrets + binaries).
PRESERVE = {
    ".env", "lunch.db", "ngrok.exe",
    "tests/data/real_cards.xlsx",
}


def _zip_url() -> str:
    return f"https://github.com/{GITHUB_REPO}/archive/refs/heads/{GITHUB_BRANCH}.zip"


def _download(url: str) -> bytes:
    # Try certifi first (Windows often can't verify via the system store).
    contexts = []
    try:
        import certifi
        contexts.append(ssl.create_default_context(cafile=certifi.where()))
    except Exception:  # noqa: BLE001
        pass
    contexts.append(None)
    unver = ssl.create_default_context()
    unver.check_hostname = False
    unver.verify_mode = ssl.CERT_NONE
    contexts.append(unver)

    last = None
    for ctx in contexts:
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "lunch-update"})
            with urllib.request.urlopen(req, timeout=120, context=ctx) as r:
                return r.read()
        except Exception as exc:  # noqa: BLE001
            last = exc
    raise RuntimeError(f"download failed: {last}")


def _copy_tree(src: Path, dst: Path) -> int:
    """Copy src dir onto dst dir (overwrite files); returns files copied."""
    count = 0
    for item in src.rglob("*"):
        rel = item.relative_to(src)
        target = dst / rel
        if item.is_dir():
            target.mkdir(parents=True, exist_ok=True)
        else:
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(item, target)
            count += 1
    return count


def main() -> int:
    if "REPLACE_ME" in GITHUB_REPO:
        print("[update] GITHUB_REPO is not set. Edit scripts/apply_update.py or set")
        print("[update] GITHUB_REPO in update.bat, e.g. yourname/lunchFMG")
        return 2

    url = _zip_url()
    print(f"[update] downloading {url}")
    try:
        data = _download(url)
    except Exception as exc:  # noqa: BLE001
        print(f"[update] {exc}")
        print("[update] Check the repo name/branch and the kiosk's internet.")
        return 1

    zf = zipfile.ZipFile(io.BytesIO(data))
    # GitHub zips contain a single top folder like "lunchFMG-main/"
    top = zf.namelist()[0].split("/")[0]
    tmp = ROOT / ".update-tmp"
    if tmp.exists():
        shutil.rmtree(tmp)
    zf.extractall(tmp)
    extracted = tmp / top
    if not extracted.exists():
        print("[update] unexpected zip layout; aborting.")
        shutil.rmtree(tmp, ignore_errors=True)
        return 1

    copied = 0
    # whole directories
    for d in COPY_DIRS:
        src = extracted / d
        if src.exists():
            copied += _copy_tree(src, ROOT / d)
    # tests code (but NOT tests/data)
    if COPY_TESTS_CODE and (extracted / "tests").exists():
        for item in (extracted / "tests").glob("*.py"):
            shutil.copy2(item, ROOT / "tests" / item.name)
            copied += 1
    # individual files
    for f in COPY_FILES:
        src = extracted / f
        if src.exists() and f not in PRESERVE:
            shutil.copy2(src, ROOT / f)
            copied += 1

    shutil.rmtree(tmp, ignore_errors=True)
    print(f"[update] applied {copied} files from {GITHUB_REPO}@{GITHUB_BRANCH}")
    print("[update] .env, lunch.db, backups/ and ngrok.exe were left untouched.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
