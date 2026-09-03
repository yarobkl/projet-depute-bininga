"""Restore contract tests (no live DB required)."""
from __future__ import annotations

import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def read(path):
    with open(os.path.join(ROOT, path), "r", encoding="utf-8") as handle:
        return handle.read()


def test_restore_verifies_before_mutation_and_creates_safety_backup():
    source = read("restore_bininga.py")
    assert source.index("backup_bininga.verify_backup") < source.index("backup_bininga.connect_db")
    assert "_create_safety_backup() if safety_backup else None" in source


def test_restore_uses_transaction_and_preserves_operational_keys():
    source = read("restore_bininga.py")
    assert "EXCLUDED_STORE_KEYS" in source
    assert "conn.commit()" in source
    assert "conn.rollback()" in source
    assert "DELETE FROM bininga_photos" in source


if __name__ == "__main__":
    tests = [fn for name, fn in sorted(globals().items()) if name.startswith("test_") and callable(fn)]
    for test in tests:
        test(); print("OK", test.__name__)
    print(f"{len(tests)} tests restore validés")
