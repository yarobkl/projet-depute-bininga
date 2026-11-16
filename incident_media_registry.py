"""Incident media registry: metadata only, no media bytes or public URLs.

This SQLite repository is intended for a server-side CloudKit gateway. The gateway
must authenticate each admin request and enforce per-dossier permissions BEFORE
calling open_media. The first open is persisted atomically with BEGIN IMMEDIATE.
"""
import sqlite3
from datetime import datetime, timezone
from incident_retention import expires_at, register_first_open, can_read, utc


def iso(value):
    return utc(value).isoformat()


def parse(value):
    return datetime.fromisoformat(value)


class IncidentMediaRegistry:
    def __init__(self, database_path):
        self.database_path = str(database_path)

    def connect(self):
        db = sqlite3.connect(self.database_path, timeout=15, isolation_level=None)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA busy_timeout=15000")
        return db

    def initialize(self):
        with self.connect() as db:
            db.execute("""CREATE TABLE IF NOT EXISTS incident_media (
                id TEXT PRIMARY KEY,
                dossier_id TEXT NOT NULL,
                cloudkit_record_id TEXT NOT NULL UNIQUE,
                received_at TEXT NOT NULL,
                first_opened_at TEXT,
                expires_at TEXT NOT NULL,
                deleted_at TEXT,
                deletion_error TEXT
            )""")
            db.execute("CREATE INDEX IF NOT EXISTS incident_media_expiry ON incident_media(expires_at,deleted_at)")

    def register(self, media_id, dossier_id, record_id, received_at):
        if not all(isinstance(x, str) and x.strip() for x in (media_id, dossier_id, record_id)):
            raise ValueError("Missing media identifiers")
        with self.connect() as db:
            db.execute("INSERT INTO incident_media(id,dossier_id,cloudkit_record_id,received_at,expires_at) VALUES(?,?,?,?,?)",
                       (media_id, dossier_id, record_id, iso(received_at), iso(expires_at(received_at))))

    def open_media(self, media_id, dossier_id, now):
        """Call only after server-side admin authorization; returns CloudKit record ID."""
        now = utc(now)
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            try:
                row = db.execute("SELECT * FROM incident_media WHERE id=? AND dossier_id=?", (media_id, dossier_id)).fetchone()
                if row is None:
                    raise KeyError("Media not found")
                received = parse(row["received_at"])
                first = parse(row["first_opened_at"]) if row["first_opened_at"] else None
                if not can_read(received, first, now, parse(row["deleted_at"]) if row["deleted_at"] else None):
                    raise PermissionError("Media unavailable or expired")
                first = register_first_open(received, first, now)
                expiry = expires_at(received, first)
                db.execute("UPDATE incident_media SET first_opened_at=?,expires_at=? WHERE id=?",
                           (iso(first), iso(expiry), media_id))
                db.execute("COMMIT")
                return row["cloudkit_record_id"]
            except BaseException:
                db.execute("ROLLBACK")
                raise

    def due_for_purge(self, now, limit=100):
        if limit < 1 or limit > 1000:
            raise ValueError("Invalid purge batch size")
        with self.connect() as db:
            rows = db.execute("SELECT id,cloudkit_record_id FROM incident_media WHERE deleted_at IS NULL AND expires_at<=? ORDER BY expires_at LIMIT ?",
                              (iso(now), limit)).fetchall()
            return [dict(row) for row in rows]

    def mark_deleted(self, media_id, now):
        """Call ONLY after CloudKit confirms deletion or record absence."""
        with self.connect() as db:
            db.execute("UPDATE incident_media SET deleted_at=?,deletion_error=NULL WHERE id=? AND deleted_at IS NULL",
                       (iso(now), media_id))

    def mark_purge_failed(self, media_id, message):
        with self.connect() as db:
            db.execute("UPDATE incident_media SET deletion_error=? WHERE id=? AND deleted_at IS NULL",
                       (str(message)[:500], media_id))
