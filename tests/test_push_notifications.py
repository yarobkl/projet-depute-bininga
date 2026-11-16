import io
import json
import unittest
from types import SimpleNamespace
from unittest.mock import patch
import push_notifications as push

class Handler:
    command = 'POST'
    path = '/api/push/admin'
    headers = {'Content-Length': '2'}
    client_address = ('127.0.0.1', 1)
    def __init__(self): self.rfile = io.BytesIO(b'{}'); self.response = None
    def _guard(self, **kwargs): return False
    def _json(self, data, status=200): self.response = (status,data)

class PushSecurityTests(unittest.TestCase):
    def test_unauthenticated_admin_has_no_database_access(self):
        h=Handler(); server=SimpleNamespace(get_session=lambda token:None)
        self.assertTrue(push.handle(server,h)); self.assertEqual(h.response[0],401)
    def test_secondary_admin_is_rejected(self):
        h=Handler(); server=SimpleNamespace(get_session=lambda token:{'username':'secondary'})
        with patch('admin_owners.is_owner_session',return_value=False): push.handle(server,h)
        self.assertEqual(h.response[0],403)
    def test_missing_csrf_cannot_send_even_for_owner(self):
        h=Handler(); server=SimpleNamespace(get_session=lambda token:{'csrf_token':'secret'})
        with patch('admin_owners.is_owner_session',return_value=True): push.handle(server,h)
        self.assertEqual(h.response[0],403)
    def test_payload_limits(self):
        for data in ({},{'title':'x'*101,'body':'ok'},{'title':'ok','body':'x'*501}):
            with self.assertRaises(ValueError): push.validate_message(data)
        self.assertEqual(push.validate_message({'title':' Bonjour ','body':' Message '}),('Bonjour','Message'))
    def test_oversized_request_rejected_before_processing(self):
        h=Handler(); h.headers={'Content-Length':'5000'}
        push.handle(SimpleNamespace(),h); self.assertEqual(h.response[0],413)

if __name__=='__main__': unittest.main()
