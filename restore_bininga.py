#!/usr/bin/env python3
"""Verified BININGA database restore.

Restore is deliberately explicit and fail-safe:
1. verify archive hashes/manifest;
2. create a pre-restore safety backup;
3. replace durable business store/photos inside one DB transaction;
4. preserve excluded operational keys such as sessions/app_config.
"""
from __future__ import annotations

import argparse
import json
import tempfile
import zipfile
from pathlib import Path

import backup_bininga


def _read_backup_file(source: Path, name: str) -> bytes:
    if source.is_dir():
        return (source / name).read_bytes()
    with zipfile.ZipFile(source, "r") as archive:
        return archive.read(name)


def _load_payload(source: Path):
    manifest = backup_bininga.verify_backup(source)
    store = json.loads(_read_backup_file(source, "bininga_store.json").decode("utf-8"))
    photos = []
    for photo in manifest.get("photos", []):
        photos.append((
            str(photo["id"]),
            _read_backup_file(source, photo["file"]),
            str(photo.get("content_type") or "application/octet-stream"),
        ))
    return manifest, store, photos


def _create_safety_backup() -> Path:
    root = backup_bininga.backup_root()
    root.mkdir(parents=True, exist_ok=True)
    dest = backup_bininga.export_backup()
    return dest


def restore(source: Path, *, safety_backup: bool = True) -> dict:
    source = Path(source).expanduser().resolve()
    manifest, store, photos = _load_payload(source)
    safety = _create_safety_backup() if safety_backup else None

    backend, conn = backup_bininga.connect_db()
    try:
        try:
            conn.autocommit = False
        except Exception:
            pass
        with conn.cursor() as cur:
            key_col = "`key`" if backend == "mysql" else '"key"'
            cur.execute(f"SELECT {key_col} FROM bininga_store")
            existing_keys = [str(row[0]) for row in cur.fetchall()]
            for key in existing_keys:
                if key in backup_bininga.EXCLUDED_STORE_KEYS:
                    continue
                placeholder = "%s"
                cur.execute(f"DELETE FROM bininga_store WHERE {key_col}={placeholder}", (key,))

            for key, value in sorted(store.items()):
                payload = json.dumps(value, ensure_ascii=False)
                if backend == "mysql":
                    cur.execute(
                        "INSERT INTO bininga_store (`key`, data) VALUES (%s,%s) ON DUPLICATE KEY UPDATE data=VALUES(data)",
                        (key, payload),
                    )
                else:
                    cur.execute(
                        'INSERT INTO bininga_store ("key", data) VALUES (%s,%s) ON CONFLICT ("key") DO UPDATE SET data=EXCLUDED.data',
                        (key, payload),
                    )

            cur.execute("DELETE FROM bininga_photos")
            for photo_id, raw, content_type in photos:
                cur.execute(
                    "INSERT INTO bininga_photos (id, data, content_type) VALUES (%s,%s,%s)",
                    (photo_id, raw, content_type),
                )
        conn.commit()
    except Exception:
        try:
            conn.rollback()
        except Exception:
            pass
        raise
    finally:
        try:
            conn.close()
        except Exception:
            pass

    return {
        "ok": True,
        "restored_store_count": len(store),
        "restored_photo_count": len(photos),
        "source_created_at": manifest.get("created_at", ""),
        "safety_backup": str(safety) if safety else "",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Restauration vérifiée BININGA")
    parser.add_argument("source", type=Path, help="Dossier ou ZIP de sauvegarde vérifié")
    parser.add_argument("--no-safety-backup", action="store_true", help="Désactiver la sauvegarde pré-restauration (déconseillé)")
    args = parser.parse_args()
    result = restore(args.source, safety_backup=not args.no_safety_backup)
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
