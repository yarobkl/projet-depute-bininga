#!/usr/bin/env python3
"""
Create a clean client copy of this project.

Usage:
  python scripts/create_client_copy.py clients/template.client.json ../client-demo

The script copies the codebase, excludes runtime/sensitive files, applies basic
brand replacements in text files, and writes a starter .env for the new client.
"""

from __future__ import annotations

import json
import os
import shutil
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

EXCLUDED_DIRS = {
    ".git",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    "node_modules",
    "dist",
}

EXCLUDED_FILES = {
    ".env",
    ".DS_Store",
    "attacks.log",
    "users.json",
    "sessions.json",
    "contacts.json",
    "audit.log",
    "blocked_ips.json",
    "attack_scores.json",
    "news_monitor.json",
    "editorial.json",
    "crm.json",
    "news.db",
}

EXCLUDED_SUFFIXES = {
    ".db",
    ".db-shm",
    ".db-wal",
    ".log",
}

TEXT_EXTENSIONS = {
    ".py",
    ".html",
    ".css",
    ".js",
    ".json",
    ".md",
    ".txt",
    ".xml",
    ".toml",
    ".yml",
    ".yaml",
}


def load_config(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def should_skip(path: Path) -> bool:
    parts = set(path.relative_to(ROOT).parts)
    if parts & EXCLUDED_DIRS:
        return True
    return (
        path.name in EXCLUDED_FILES
        or path.name.endswith("_backup.json")
        or any(path.name.endswith(suffix) for suffix in EXCLUDED_SUFFIXES)
    )


def copy_project(target: Path) -> None:
    if target.exists() and any(target.iterdir()):
        raise SystemExit(f"Target already exists and is not empty: {target}")
    target.mkdir(parents=True, exist_ok=True)

    for src in ROOT.rglob("*"):
        if should_skip(src):
            continue
        rel = src.relative_to(ROOT)
        dst = target / rel
        if src.is_dir():
            dst.mkdir(parents=True, exist_ok=True)
        elif src.is_file():
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)


def replacements_from_config(config: dict) -> dict[str, str]:
    brand = config.get("brand", {})
    old_full_name = brand.get("old_full_name", "Ange Aimé Wilfrid BININGA")
    new_full_name = brand.get("new_full_name", "Nom Complet du Client")

    return {
        old_full_name: new_full_name,
        "bininga.cg": config.get("public_domain", "https://client.cg").replace("https://", ""),
    }


def apply_text_replacements(target: Path, replacements: dict[str, str]) -> None:
    for file_path in target.rglob("*"):
        if not file_path.is_file() or file_path.suffix.lower() not in TEXT_EXTENSIONS:
            continue
        try:
            text = file_path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        new_text = text
        for old, new in replacements.items():
            new_text = new_text.replace(old, new)
        if new_text != text:
            file_path.write_text(new_text, encoding="utf-8")


def write_env(target: Path, config: dict) -> None:
    origins = ",".join(
        value
        for value in [config.get("public_domain"), config.get("public_domain_www")]
        if value
    )
    env = f"""# Generated for {config.get('project_name', 'client project')}
# Fill real secrets before deployment. Do not commit this file.

MYSQL_HOST=localhost
MYSQL_PORT=3306
MYSQL_DATABASE={config.get('mysql_database', 'cpaneluser_client')}
MYSQL_USER={config.get('mysql_user', 'cpaneluser_client')}
MYSQL_PASSWORD={config.get('mysql_password_placeholder', 'CHANGE_ME')}

BININGA_USER={config.get('admin_user', 'admin')}
BININGA_PASS={config.get('admin_password_placeholder', 'CHANGE_ME')}
ADMIN_SECRET_PATH={config.get('admin_secret_path', 'espace-prive-client')}
BININGA_ORIGINS={origins}

NOTIF_EMAIL_FROM=
NOTIF_EMAIL_PASS=
NOTIF_EMAIL_TO={config.get('notification_email_to', '')}

BININGA_FORCE_FILE_SYNC=0
"""
    (target / ".env").write_text(env, encoding="utf-8")


def main(argv: list[str]) -> int:
    if len(argv) != 3:
        print(__doc__.strip())
        return 2

    config_path = Path(argv[1]).expanduser()
    target = Path(argv[2]).expanduser().resolve()
    if not config_path.is_absolute():
        config_path = (Path.cwd() / config_path).resolve()

    config = load_config(config_path)
    copy_project(target)
    apply_text_replacements(target, replacements_from_config(config))
    write_env(target, config)

    print(f"Client copy created: {target}")
    print("Next: edit data.json, replace images, fill .env secrets, run tests.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
