import os
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from incident_media_registry import IncidentMediaRegistry


class RegistryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.registry = IncidentMediaRegistry(os.path.join(self.tmp.name, "media.db"))
        self.registry.initialize()
        self.received = datetime(2026, 11, 16, 12, tzinfo=timezone.utc)
        self.registry.register("m1", "d1", "ck-record-1", self.received)

    def test_open_starts_48_hour_expiry(self):
        opened = self.received + timedelta(hours=1)
        self.assertEqual(self.registry.open_media("m1", "d1", opened), "ck-record-1")
        self.assertEqual(self.registry.due_for_purge(opened + timedelta(hours=47)), [])
        self.assertEqual(len(self.registry.due_for_purge(opened + timedelta(hours=48))), 1)

    def test_repeat_open_does_not_extend_expiry(self):
        opened = self.received + timedelta(hours=1)
        self.registry.open_media("m1", "d1", opened)
        self.registry.open_media("m1", "d1", opened + timedelta(hours=5))
        self.assertEqual(len(self.registry.due_for_purge(opened + timedelta(hours=48))), 1)

    def test_unopened_expires_after_seven_days(self):
        self.assertEqual(len(self.registry.due_for_purge(self.received + timedelta(days=7))), 1)
        with self.assertRaises(PermissionError):
            self.registry.open_media("m1", "d1", self.received + timedelta(days=7))

    def test_wrong_dossier_cannot_open(self):
        with self.assertRaises(KeyError):
            self.registry.open_media("m1", "other", self.received)

    def test_deleted_media_cannot_open(self):
        self.registry.mark_deleted("m1", self.received)
        with self.assertRaises(PermissionError):
            self.registry.open_media("m1", "d1", self.received)

    def test_failed_purge_remains_due(self):
        expired = self.received + timedelta(days=7)
        self.registry.mark_purge_failed("m1", "temporary CloudKit outage")
        self.assertEqual(len(self.registry.due_for_purge(expired)), 1)
        self.registry.mark_deleted("m1", expired)
        self.assertEqual(self.registry.due_for_purge(expired), [])


if __name__ == "__main__":
    unittest.main()
