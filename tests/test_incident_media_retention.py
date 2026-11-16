import unittest
from datetime import datetime, timedelta, timezone
from incident_retention import expires_at, register_first_open, can_read

class RetentionTests(unittest.TestCase):
    def setUp(self): self.received = datetime(2026,11,16,12,tzinfo=timezone.utc)
    def test_unopened_expires_at_seven_days(self):
        self.assertEqual(expires_at(self.received),self.received+timedelta(days=7))
    def test_first_view_expires_at_48_hours(self):
        self.assertEqual(expires_at(self.received,self.received+timedelta(hours=1)),self.received+timedelta(hours=49))
    def test_late_view_cannot_exceed_seven_days(self):
        self.assertEqual(expires_at(self.received,self.received+timedelta(days=6)),self.received+timedelta(days=7))
    def test_repeat_view_does_not_extend_deadline(self):
        opened=self.received+timedelta(hours=1)
        self.assertEqual(register_first_open(self.received,opened,self.received+timedelta(hours=3)),opened)
    def test_expired_link_is_denied_at_boundary(self):
        self.assertFalse(can_read(self.received,None,self.received+timedelta(days=7)))
        with self.assertRaises(PermissionError):
            register_first_open(self.received,None,self.received+timedelta(days=7))
    def test_deleted_media_is_denied(self):
        self.assertFalse(can_read(self.received,None,self.received,deleted_at=self.received))
    def test_naive_timestamps_rejected(self):
        with self.assertRaises(ValueError): expires_at(datetime(2026,11,16))
    def test_open_before_reception_rejected(self):
        with self.assertRaises(ValueError): expires_at(self.received,self.received-timedelta(seconds=1))


    def test_pre_receipt_access_denied(self):
        self.assertFalse(can_read(self.received,None,self.received-timedelta(seconds=1)))
        with self.assertRaises(ValueError):
            register_first_open(self.received,None,self.received-timedelta(seconds=1))
    def test_first_open_at_expiry_rejected(self):
        with self.assertRaises(PermissionError):
            register_first_open(self.received,None,self.received+timedelta(days=7))
    def test_first_open_after_expiry_is_invalid(self):
        with self.assertRaises(ValueError):
            expires_at(self.received,self.received+timedelta(days=8))
    def test_first_open_utc_normalization(self):
        from datetime import timezone
        opened=self.received+timedelta(hours=1)
        self.assertEqual(register_first_open(self.received,opened,self.received+timedelta(hours=2)),opened)
    def test_naive_now_rejected(self):
        with self.assertRaises(ValueError):
            can_read(self.received,None,datetime(2026,11,16))

if __name__=="__main__": unittest.main()
