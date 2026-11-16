import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
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



class BroadcastTests(unittest.TestCase):
    def request(self, payload):
        from unittest.mock import MagicMock
        h = Handler()
        raw = json.dumps(payload).encode()
        h.headers = {'Content-Length': str(len(raw)), 'X-CSRF-Token': 'csrf'}
        h.rfile = io.BytesIO(raw)
        server = SimpleNamespace(get_session=lambda token: {'csrf_token': 'csrf'}, audit_log=MagicMock())
        conn = MagicMock()
        cursor = conn.cursor.return_value.__enter__.return_value
        return h, server, conn, cursor

    def test_broadcast_snapshots_all_subscribers_without_sending_in_enqueue_request(self):
        h, server, conn, c = self.request({'action':'send','id':'11111111-1111-4111-8111-111111111111','audience':'all_authorized'})
        c.fetchone.side_effect = [(3,), (1, 3)]
        with patch('admin_owners.is_owner_session',return_value=True), patch.object(push,'connection',return_value=conn), patch.dict('os.environ',{'BININGA_APNS_PRIVATE_KEY':'test-only'}), patch.object(push,'send_apns') as transport:
            push.handle(server,h)
        self.assertEqual(h.response[0],200)
        self.assertEqual(h.response[1]['result'],{'total':3,'pending':3})
        transport.assert_not_called()
        sql = ' '.join(call.args[0] for call in c.execute.call_args_list)
        self.assertIn("status='draft'",sql)
        self.assertIn('devices.active=TRUE',sql)
        self.assertIn('CROSS JOIN',sql)

    def test_device_specific_old_requests_cannot_accidentally_broadcast(self):
        h, server, conn, c = self.request({'action':'send','id':'11111111-1111-4111-8111-111111111111','device':'old-device'})
        with patch('admin_owners.is_owner_session',return_value=True), patch.object(push,'connection',return_value=conn), patch.dict('os.environ',{'BININGA_APNS_PRIVATE_KEY':'test-only'}):
            push.handle(server,h)
        self.assertEqual(h.response[0],400)
        c.execute.assert_not_called()

    def test_no_subscriber_means_no_enqueue(self):
        h, server, conn, c = self.request({'action':'send','id':'11111111-1111-4111-8111-111111111111','audience':'all_authorized'})
        c.fetchone.return_value = (0,)
        with patch('admin_owners.is_owner_session',return_value=True), patch.object(push,'connection',return_value=conn), patch.dict('os.environ',{'BININGA_APNS_PRIVATE_KEY':'test-only'}):
            push.handle(server,h)
        self.assertEqual(h.response[0],400)
        self.assertEqual(c.execute.call_count,1)

    def test_second_click_does_not_enqueue_an_already_claimed_draft(self):
        h, server, conn, c = self.request({'action':'send','id':'11111111-1111-4111-8111-111111111111','audience':'all_authorized'})
        c.fetchone.side_effect = [(3,), (0, 0)]
        with patch('admin_owners.is_owner_session',return_value=True), patch.object(push,'connection',return_value=conn), patch.dict('os.environ',{'BININGA_APNS_PRIVATE_KEY':'test-only'}), patch.object(push,'send_apns') as transport:
            push.handle(server,h)
        self.assertEqual(h.response[0],400)
        server.audit_log.assert_not_called()
        transport.assert_not_called()

    def test_fanout_counts_failures_and_deactivates_expired_devices(self):
        from unittest.mock import MagicMock
        conn=MagicMock();c=conn.cursor.return_value.__enter__.return_value
        c.fetchone.return_value=('Title','Body')
        c.fetchall.side_effect=[ [('one','token-one'),('two','token-two'),('three','token-three')], [('accepted',1),('rejected',1),('unknown',1)] ]
        def transport(token,*args):
            if token == 'token-one': return 200,''
            if token == 'token-two': return 410,'Unregistered'
            raise TimeoutError()
        with patch.object(push,'send_apns',side_effect=transport) as send:
            result=push.dispatch_batch(conn,'message')
        self.assertEqual(result,{'accepted':1,'rejected':1,'unknown':1,'skipped':0,'pending':0,'total':3})
        self.assertEqual(send.call_count,3)
        deactivations=[call for call in c.execute.call_args_list if 'SET active=FALSE' in call.args[0]]
        self.assertEqual(len(deactivations),1)
        self.assertEqual(deactivations[0].args[1],('two',))

    def test_completed_batch_does_not_resend(self):
        from unittest.mock import MagicMock
        conn=MagicMock();c=conn.cursor.return_value.__enter__.return_value
        c.fetchone.return_value=('Title','Body')
        c.fetchall.side_effect=[[], [('accepted',3)]]
        with patch.object(push,'send_apns') as send:
            self.assertEqual(push.dispatch_batch(conn,'message')['pending'],0)
        send.assert_not_called()

    def test_provider_token_is_reused_for_the_broadcast_and_rotated_on_expiry(self):
        with patch.object(push,'_TOKEN_CACHE',None), patch.dict('os.environ',{'BININGA_APNS_PRIVATE_KEY':'test-key'}), patch('jwt.encode',side_effect=['first','second']) as encode, patch.object(push.time,'time',side_effect=[1000,1001,4000]):
            self.assertEqual(push.provider_token(),'first')
            self.assertEqual(push.provider_token(),'first')
            self.assertEqual(push.provider_token(),'second')
            self.assertEqual(encode.call_count,2)

if __name__=='__main__': unittest.main()
