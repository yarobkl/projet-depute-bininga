#!/usr/bin/env python3
"""Sauvegarde durable du contenu BININGA.

Exporte la base MySQL/PostgreSQL dans backups/ avec :
- bininga_store.json : contenus, utilisateurs, contacts, CRM
- photos/ : toutes les images stockées en base
- manifest.json : résumé vérifiable
"""

import argparse
import hashlib
import io
import json
import os
import re
import shutil
import sys
import zipfile
from datetime import datetime, timezone
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent
KEEP_DEFAULT = 14
EXCLUDED_STORE_KEYS = {"sessions", "app_config"}


def backup_root() -> Path:
    """Répertoire des copies serveur, configurable et compatible Vercel."""
    explicit = os.environ.get("BININGA_BACKUP_DIR", "").strip()
    if explicit:
        return Path(explicit).expanduser().resolve()
    data_dir = os.environ.get("DATA_DIR", "").strip()
    if data_dir and data_dir != ".":
        return (Path(data_dir).expanduser().resolve() / "backups")
    return BASE_DIR / "backups"


# Compatibilité avec les tâches cron existantes qui importent cette constante.
BACKUP_ROOT = backup_root()


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


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def collect_snapshot():
    """Collecte une sauvegarde cohérente sans écrire sur le disque.

    Le résultat alimente aussi bien les copies serveur historiques que
    l'archive téléchargeable depuis l'administration.
    """
    load_env_file()
    backend, conn = connect_db()
    created = datetime.now(timezone.utc).replace(microsecond=0)
    stamp = created.strftime("%Y%m%d-%H%M%SZ")
    manifest = {
        "format": "bininga-backup",
        "format_version": 2,
        "created_at": created.isoformat().replace("+00:00", "Z"),
        "backend": backend,
        "store_count": 0,
        "photo_count": 0,
        "photos": [],
        "files": {},
        "excluded_store_keys": sorted(EXCLUDED_STORE_KEYS),
    }
    files = {}
    try:
        with conn.cursor() as cur:
            key_col = "`key`" if backend == "mysql" else "key"
            cur.execute(f"SELECT {key_col}, data FROM bininga_store ORDER BY {key_col}")
            store = {}
            for key, data in cur.fetchall():
                if str(key) in EXCLUDED_STORE_KEYS:
                    continue
                try:
                    store[str(key)] = json.loads(data) if isinstance(data, str) else data
                except Exception:
                    store[str(key)] = data
            store_bytes = (json.dumps(store, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
            files["bininga_store.json"] = store_bytes
            manifest["store_count"] = len(store)

            cur.execute("SELECT id, data, content_type FROM bininga_photos ORDER BY id")
            used_names = set()
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
                if filename in used_names:
                    filename = f"{safe_name(str(photo_id))}-{_sha256(raw)[:8]}{ext}"
                used_names.add(filename)
                relative = f"photos/{filename}"
                files[relative] = raw
                manifest["photos"].append({
                    "id": str(photo_id),
                    "file": relative,
                    "content_type": str(content_type or "application/octet-stream"),
                    "bytes": len(raw),
                    "sha256": _sha256(raw),
                })
    finally:
        try:
            conn.close()
        except Exception:
            pass

    data_json = BASE_DIR / "data.json"
    if data_json.exists():
        files["data.json.snapshot"] = data_json.read_bytes()

    manifest["photo_count"] = len(manifest["photos"])
    manifest["files"] = {
        name: {"bytes": len(content), "sha256": _sha256(content)}
        for name, content in sorted(files.items())
    }
    return f"bininga-{stamp}", manifest, files


def build_backup_archive():
    """Produit une archive ZIP complète et vérifiable en mémoire."""
    name, manifest, files = collect_snapshot()
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
        for relative, content in sorted(files.items()):
            archive.writestr(relative, content)
        archive.writestr(
            "manifest.json",
            (json.dumps(manifest, ensure_ascii=False, indent=2) + "\n").encode("utf-8"),
        )
    return f"{name}.zip", stream.getvalue(), manifest


def export_backup() -> Path:
    """Crée une copie serveur. Sur Vercel elle est temporaire (/tmp)."""
    name, manifest, files = collect_snapshot()
    dest = backup_root() / name
    photos_dir = dest / "photos"
    photos_dir.mkdir(parents=True, exist_ok=False)
    for relative, content in files.items():
        target = dest / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(content)
    (dest / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return dest


def verify_backup(source: Path):
    """Vérifie structure, compteurs et empreintes d'un dossier ou ZIP."""
    source = Path(source)
    archive = None
    if source.is_dir():
        manifest = json.loads((source / "manifest.json").read_text(encoding="utf-8"))

        def read_file(name):
            target = (source / name).resolve()
            target.relative_to(source.resolve())
            return target.read_bytes()
    elif source.is_file() and zipfile.is_zipfile(source):
        archive = zipfile.ZipFile(source, "r")
        try:
            names = set(archive.namelist())
            if any(name.startswith(("/", "\\")) or ".." in Path(name).parts for name in names):
                raise ValueError("Archive invalide : chemin dangereux")
            manifest = json.loads(archive.read("manifest.json").decode("utf-8"))
        except Exception:
            archive.close()
            raise

        def read_file(name):
            return archive.read(name)
    else:
        raise ValueError("Sauvegarde introuvable ou format non reconnu")

    try:
        if manifest.get("format") != "bininga-backup" or int(manifest.get("format_version", 0)) < 2:
            raise ValueError("Format de sauvegarde non reconnu")
        expected_files = manifest.get("files")
        if not isinstance(expected_files, dict) or "bininga_store.json" not in expected_files:
            raise ValueError("Manifest incomplet")
        for name, expected in expected_files.items():
            content = read_file(name)
            if len(content) != int(expected.get("bytes", -1)):
                raise ValueError(f"Taille invalide : {name}")
            if _sha256(content) != expected.get("sha256"):
                raise ValueError(f"Empreinte invalide : {name}")
        store = json.loads(read_file("bininga_store.json").decode("utf-8"))
        if len(store) != int(manifest.get("store_count", -1)):
            raise ValueError("Compteur de données incohérent")
        photos = manifest.get("photos", [])
        if len(photos) != int(manifest.get("photo_count", -1)):
            raise ValueError("Compteur de photos incohérent")
        return manifest
    finally:
        if archive is not None:
            archive.close()


def prune_old_backups(keep: int) -> None:
    root = backup_root()
    if keep <= 0 or not root.exists():
        return
    backups = sorted(p for p in root.glob("bininga-*") if p.is_dir())
    for old in backups[:-keep]:
        shutil.rmtree(old, ignore_errors=True)


def main() -> int:
    parser = argparse.ArgumentParser(description="Sauvegarde DB/photos BININGA")
    parser.add_argument("--keep", type=int, default=KEEP_DEFAULT, help="Nombre de sauvegardes à conserver")
    parser.add_argument("--archive", type=Path, help="Créer également une archive ZIP téléchargeable")
    parser.add_argument("--verify", type=Path, help="Vérifier une sauvegarde existante sans la restaurer")
    args = parser.parse_args()

    if args.verify:
        manifest = verify_backup(args.verify)
        print(
            f"OK vérifiée={args.verify} store={manifest['store_count']} "
            f"photos={manifest['photo_count']}"
        )
        return 0

    if args.archive:
        filename, content, manifest = build_backup_archive()
        target = args.archive / filename if args.archive.is_dir() else args.archive
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(content)
        print(
            f"OK archive={target} store={manifest['store_count']} "
            f"photos={manifest['photo_count']}"
        )
        return 0

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
