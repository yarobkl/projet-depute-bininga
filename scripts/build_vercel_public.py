"""Promote browser assets to Vercel's CDN during the build.

The Python project uses a custom WSGI entrypoint, so files living only in
``static/`` are otherwise served by the Python function. That adds a serverless
invocation for every JS/CSS request. Vercel serves files generated under
``public/`` directly from its edge network.

Only immutable browser assets are promoted here. Authentication HTML and all
API/dynamic routes remain handled by the application so the existing security
and no-store behaviour is preserved.
"""

from __future__ import annotations

import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "static"
DEST = ROOT / "public" / "static"
ALLOWED_SUFFIXES = {".js", ".css"}


def main() -> None:
    if DEST.exists():
        shutil.rmtree(DEST)
    DEST.mkdir(parents=True, exist_ok=True)

    copied = 0
    for source in SOURCE.rglob("*"):
        if not source.is_file() or source.suffix.lower() not in ALLOWED_SUFFIXES:
            continue
        relative = source.relative_to(SOURCE)
        target = DEST / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
        copied += 1

    print(f"[VERCEL BUILD] {copied} JS/CSS asset(s) promoted to public/static for CDN delivery")


if __name__ == "__main__":
    main()
