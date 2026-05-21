#!/usr/bin/env python3
"""Sauvegarde durable du contenu BININGA.

Exporte la base MySQL/PostgreSQL dans backups/ avec :
- bininga_store.json : contenus, utilisateurs, contacts, CRM
- photos/ : toutes les images stockées en base
- manifest.json : résumé vérifiable
"""

import argparse
import base64
import json
import os
import re
import shutil
import sys
from datetime import datetime
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent
BACKUP_ROOT = BASE_DIR / "backups"
KEEP_DEFAULT = 14


def load_env_file() -> None:
    env_path = BASE_DIR / ".env"
    if not env_path.exists():
        return
    for raw in env_path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, val = line.split("=", 1)
        key = key.strip()
        val = val.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = val


def safe_name(value: str) -> str:
    value = re.sub(r"[^A-Za-z0-9_.-]+", "_", value).strip("._")
    return value or "photo"


def db_config():
    database_url = os.environ.get("DATABASE_URL", "").strip()
    if database_url:
        if database_url.startswith(("mysql://", "mariadb://")):
            return "mysql_url", database_url
        return "postgres_url", database_url

    if os.environ.get("MYSQL_DATABASE") and os.environ.get("MYSQL_USER"):
        return "mysql", {
            "host": os.environ.get("MYSQL_HOST", "localhost"),
            "port": int(os.environ.get("MYSQL_PORT", "3306") or 3306),
            "user": os.environ["MYSQL_USER"],
            "password": os.environ.get("MYSQL_PASSWORD", ""),
            "database": os.environ["MYSQL_DATABASE"],
        }
    return None, None


def connect_db():
    backend, cfg = db_config()
    if backend is None:
        raise RuntimeError("Aucune base configurée (.env / DATABASE_URL / MYSQL_*)")

    if backend in ("mysql", "mysql_url"):
        import pymysql
        from urllib.parse import urlparse, unquote

        if backend == "mysql_url":
            parsed = urlparse(cfg)
            return "mysql", pymysql.connect(
                host=parsed.hostname or "localhost",
                port=parsed.port or 3306,
                user=unquote(parsed.username or ""),
                password=unquote(parsed.password or ""),
                database=(parsed.path or "").lstrip("/"),
                charset="utf8mb4",
                autocommit=True,
                connect_timeout=8,
            )
        return "mysql", pymysql.connect(
            host=cfg["host"],
            port=cfg["port"],
            user=cfg["user"],
            password=cfg["password"],
            database=cfg["database"],
            charset="utf8mb4",
            autocommit=True,
            connect_timeout=8,
        )

    import psycopg2

    url = cfg.replace("postgres://", "postgresql://", 1)
    conn = psycopg2.connect(url, connect_timeout=8)
    conn.autocommit = True
    return "postgresql", conn


def export_backup() -> Path:
    load_env_file()
    backend, conn = connect_db()

    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    dest = BACKUP_ROOT / f"bininga-{stamp}"
    photos_dir = dest / "photos"
    photos_dir.mkdir(parents=True, exist_ok=False)

    manifest = {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "backend": backend,
        "store_count": 0,
        "photo_count": 0,
        "photos": [],
    }

    with conn.cursor() as cur:
        key_col = "`key`" if backend == "mysql" else "key"
        cur.execute(f"SELECT {key_col}, data FROM bininga_store ORDER BY {key_col}")
        rows = cur.fetchall()
        store = {}
        for key, data in rows:
            try:
                store[key] = json.loads(data)
            except Exception:
                store[key] = data
        manifest["store_count"] = len(store)
        (dest / "bininga_store.json").write_text(
            json.dumps(store, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        cur.execute("SELECT id, data, content_type FROM bininga_photos ORDER BY id")
        for photo_id, blob, content_type in cur.fetchall():
            raw = bytes(blob)
            ext = {
                "image/jpeg": ".jpg",
                "image/png": ".png",
                "image/webp": ".webp",
                "image/gif": ".gif",
                "image/svg+xml": ".svg",
            }.get(content_type, ".bin")
            filename = safe_name(str(photo_id)) + ext
            (photos_dir / filename).write_bytes(raw)
            manifest["photos"].append({
                "id": photo_id,
                "file": f"photos/{filename}",
                "content_type": content_type,
                "bytes": len(raw),
            })

    manifest["photo_count"] = len(manifest["photos"])
    (dest / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    data_json = BASE_DIR / "data.json"
    if data_json.exists():
        shutil.copy2(data_json, dest / "data.json.snapshot")

    return dest


def prune_old_backups(keep: int) -> None:
    if keep <= 0 or not BACKUP_ROOT.exists():
        return
    backups = sorted(p for p in BACKUP_ROOT.glob("bininga-*") if p.is_dir())
    for old in backups[:-keep]:
        shutil.rmtree(old, ignore_errors=True)


def main() -> int:
    parser = argparse.ArgumentParser(description="Sauvegarde DB/photos BININGA")
    parser.add_argument("--keep", type=int, default=KEEP_DEFAULT, help="Nombre de sauvegardes à conserver")
    args = parser.parse_args()

    dest = export_backup()
    prune_old_backups(args.keep)

    manifest = json.loads((dest / "manifest.json").read_text(encoding="utf-8"))
    print(
        f"OK backup={dest} store={manifest['store_count']} photos={manifest['photo_count']}"
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"ERREUR sauvegarde BININGA: {exc}", file=sys.stderr)
        raise SystemExit(1)
