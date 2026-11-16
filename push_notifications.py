"""APNs transport and owner-only notification drafts. Never log device tokens or keys."""
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
import os
import re
import secrets
import time
import threading
import uuid
from urllib.parse import urlparse

TOPIC = 'fr.yaroconsulting.bininga.publicapp'
_TOKEN_LOCK = threading.Lock()
_TOKEN_CACHE = None


def validate_message(data):
    title = str(data.get('title', '')).strip()
    body = str(data.get('body', '')).strip()
    if not 1 <= len(title) <= 100 or not 1 <= len(body) <= 500:
        raise ValueError('Titre (100 caractères max.) et message (500 max.) requis.')
    return title, body


def connection(server):
    conn = server._pg()
    if conn is None or getattr(server._pg_local, 'backend', '') != 'postgresql':
        raise RuntimeError('Base PostgreSQL indisponible')
    with conn.cursor() as c:
        c.execute('''CREATE TABLE IF NOT EXISTS bininga_push_devices (
            id TEXT PRIMARY KEY, token TEXT UNIQUE NOT NULL, active BOOLEAN NOT NULL DEFAULT TRUE,
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW())''')
        c.execute('''CREATE TABLE IF NOT EXISTS bininga_push_messages (
            id TEXT PRIMARY KEY, title TEXT NOT NULL, body TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'draft', result TEXT NOT NULL DEFAULT '{}',
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW())''')
        c.execute("""CREATE TABLE IF NOT EXISTS bininga_push_deliveries (
            message_id TEXT NOT NULL REFERENCES bininga_push_messages(id),
            device_id TEXT NOT NULL REFERENCES bininga_push_devices(id),
            status TEXT NOT NULL DEFAULT 'pending', reason TEXT NOT NULL DEFAULT '',
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(), PRIMARY KEY(message_id,device_id))""")
        c.execute("CREATE INDEX IF NOT EXISTS bininga_push_pending ON bininga_push_deliveries(message_id,status)")
    return conn


def provider_token():
    import jwt
    global _TOKEN_CACHE
    key = os.environ.get('BININGA_APNS_PRIVATE_KEY', '')
    if not key: raise RuntimeError('Clé APNs non configurée')
    fingerprint = hashlib.sha256(key.encode()).digest()
    now = int(time.time())
    with _TOKEN_LOCK:
        if _TOKEN_CACHE and _TOKEN_CACHE[0] == fingerprint and _TOKEN_CACHE[2] > now:
            return _TOKEN_CACHE[1]
        token = jwt.encode({'iss': 'UK4UQCQ57G', 'iat': now}, key,
            algorithm='ES256', headers={'kid': 'A2J3Z6G7WJ'})
        _TOKEN_CACHE = (fingerprint, token, now + 45 * 60)
        return token


def send_apns(token, title, body, message_id):
    import httpx
    bearer = provider_token()
    with httpx.Client(http2=True, timeout=8) as client:
        response = client.post('https://api.push.apple.com/3/device/' + token,
            headers={'authorization': 'bearer ' + bearer, 'apns-topic': TOPIC,
                     'apns-push-type': 'alert', 'apns-priority': '10',
                     'apns-collapse-id': message_id, 'apns-expiration': str(int(time.time()) + 86400)},
            json={'aps': {'alert': {'title': title, 'body': body}, 'sound': 'default'},
                  'notification_id': message_id})
    reason = ''
    if response.status_code != 200:
        try: reason = response.json().get('reason', '')
        except ValueError: reason = 'APNsError'
    return response.status_code, reason


def handle(server, handler):
    path = urlparse(handler.path).path
    if path not in ('/api/push/register', '/api/push/admin'):
        return False
    method = handler.command
    if method not in ('GET', 'POST') or (path.endswith('register') and method != 'POST'):
        handler._json({'ok': False, 'message': 'Méthode refusée'}, 405); return True
    try:
        length = int(handler.headers.get('Content-Length', '0'))
    except ValueError:
        length = -1
    if length < 0 or length > 4096:
        handler._json({'ok': False, 'message': 'Requête trop volumineuse'}, 413); return True
    if handler._guard(path=path, method=method, body_size=length): return True
    if path.endswith('admin'):
        import admin_owners
        session = server.get_session(handler.headers.get('X-Admin-Token', ''))
        if not session:
            handler._json({'ok': False, 'message': 'Connexion requise'}, 401); return True
        if not admin_owners.is_owner_session(server, session):
            handler._json({'ok': False, 'message': 'Réservé aux propriétaires'}, 403); return True
        if method == 'POST' and not (session.get('csrf_token') and secrets.compare_digest(
                session['csrf_token'], handler.headers.get('X-CSRF-Token', ''))):
            handler._json({'ok': False, 'message': 'Requête invalide (CSRF)'}, 403); return True
    try:
        data = json.loads(handler.rfile.read(length).decode()) if method == 'POST' else {}
        if not isinstance(data, dict): raise ValueError('Objet JSON requis')
        conn = connection(server)
        with conn.cursor() as c:
            if path.endswith('register'):
                installation = str(data.get('installation', ''))
                token = str(data.get('token', ''))
                if not re.fullmatch('[a-f0-9]{64}', installation) or not re.fullmatch('[a-f0-9]{32,512}', token) or len(token) % 2:
                    raise ValueError('Inscription invalide')
                ident = hashlib.sha256(installation.encode()).hexdigest()
                # Token uniqueness prevents an unrelated installation overwriting an existing device.
                c.execute('''INSERT INTO bininga_push_devices(id, token, active) VALUES (%s,%s,%s)
                    ON CONFLICT(id) DO UPDATE SET token=EXCLUDED.token, active=EXCLUDED.active, updated_at=NOW()''',
                    (ident, token, data.get('enabled') is True))
                handler._json({'ok': True, 'device_id': ident}); return True
            if method == 'GET':
                c.execute('SELECT id,title,body,status,result,created_at FROM bininga_push_messages ORDER BY created_at DESC LIMIT 50')
                messages = [dict(zip(('id','title','body','status','result','created_at'),
                    (r[0],r[1],r[2],r[3],json.loads(r[4]),r[5].isoformat()))) for r in c.fetchall()]
                c.execute('SELECT COUNT(*) FROM bininga_push_devices WHERE active=TRUE')
                audience_count = c.fetchone()[0]
                handler._json({'ok': True, 'configured': bool(os.environ.get('BININGA_APNS_PRIVATE_KEY')),
                    'messages': messages, 'audience_count': audience_count}); return True
            action = data.get('action')
            if action == 'draft':
                title, body = validate_message(data)
                ident = str(uuid.uuid4())
                c.execute('INSERT INTO bininga_push_messages(id,title,body) VALUES (%s,%s,%s)', (ident,title,body))
                handler._json({'ok': True, 'id': ident}); return True
            if action not in ('send', 'dispatch'): raise ValueError('Action inconnue')
            if not os.environ.get('BININGA_APNS_PRIVATE_KEY'): raise ValueError('Clé APNs non configurée')
            ident = str(uuid.UUID(str(data.get('id', ''))))
            if action == 'send':
                if data.get('audience') != 'all_authorized' or 'device' in data:
                    raise ValueError('Confirmez l’envoi à tous les appareils autorisés')
                c.execute('SELECT COUNT(*) FROM bininga_push_devices WHERE active=TRUE')
                if c.fetchone()[0] == 0: raise ValueError('Aucun appareil autorisé inscrit')
                # Claim the draft and freeze its opted-in audience atomically. A second click
                # cannot enqueue the same publication twice, even in another admin tab.
                c.execute("""WITH claimed AS (
                    UPDATE bininga_push_messages SET status='queued'
                    WHERE id=%s AND status='draft' RETURNING id
                ), recipients AS (
                    INSERT INTO bininga_push_deliveries(message_id,device_id)
                    SELECT claimed.id,devices.id FROM claimed CROSS JOIN bininga_push_devices devices
                    WHERE devices.active=TRUE RETURNING device_id
                ) SELECT (SELECT COUNT(*) FROM claimed),COUNT(*) FROM recipients""", (ident,))
                claimed, total = c.fetchone()
                if not claimed: raise ValueError('Brouillon absent ou déjà envoyé')
                server.audit_log('PUSH_BROADCAST', handler.client_address[0], 'Notification ' + ident + ': ' + str(total) + ' appareils')
                handler._json({'ok': True, 'status': 'queued', 'result': {'total': total, 'pending': total}}); return True
        result = dispatch_batch(conn, ident)
        handler._json({'ok': True, 'status': 'queued' if result['pending'] else 'complete', 'result': result})
        return True
    except (ValueError, UnicodeDecodeError):
        handler._json({'ok': False, 'message': 'Données invalides ou action déjà effectuée'}, 400)
    except Exception:
        handler._json({'ok': False, 'message': 'Service notifications indisponible. Aucun succès confirmé.'}, 503)
    return True



def dispatch_batch(conn, ident):
    """Bounded, resumable fan-out. Never retry a device after an ambiguous send.

    The admin keeps requesting batches until completion. If it disconnects, the
    durable queue is retained and the owner can resume it from the history.
    """
    with conn.cursor() as c:
        c.execute("SELECT title,body FROM bininga_push_messages WHERE id=%s AND status IN ('queued','complete')", (ident,))
        message = c.fetchone()
        if not message: raise ValueError('Envoi introuvable')
        c.execute("""UPDATE bininga_push_deliveries SET status='unknown',reason='InterruptedDispatch'
            WHERE message_id=%s AND status='sending' AND updated_at < NOW()-INTERVAL '2 minutes'""", (ident,))
        c.execute("""UPDATE bininga_push_deliveries delivery SET status='skipped',updated_at=NOW()
            FROM bininga_push_devices device WHERE delivery.device_id=device.id
            AND delivery.message_id=%s AND delivery.status='pending' AND device.active=FALSE""", (ident,))
        c.execute("""WITH batch AS (
            SELECT message_id,device_id FROM bininga_push_deliveries
            WHERE message_id=%s AND status='pending' ORDER BY device_id
            LIMIT 20 FOR UPDATE SKIP LOCKED
        ), claimed AS (
            UPDATE bininga_push_deliveries delivery SET status='sending',updated_at=NOW()
            FROM batch WHERE delivery.message_id=batch.message_id AND delivery.device_id=batch.device_id
            RETURNING delivery.device_id
        ) SELECT claimed.device_id,device.token FROM claimed JOIN bininga_push_devices device ON device.id=claimed.device_id""", (ident,))
        batch = c.fetchall()

    def deliver(row):
        device, token = row
        try:
            status, reason = send_apns(token, *message, ident)
            return device, 'accepted' if status == 200 else 'rejected', reason, status
        except Exception:
            return device, 'unknown', 'TransportIndeterminate', 0

    with ThreadPoolExecutor(max_workers=10) as pool:
        results = list(pool.map(deliver, batch))
    with conn.cursor() as c:
        for device, state, reason, status in results:
            c.execute("""UPDATE bininga_push_deliveries SET status=%s,reason=%s,updated_at=NOW()
                WHERE message_id=%s AND device_id=%s AND status='sending'""", (state,reason,ident,device))
            if status == 410 or reason in ('Unregistered', 'BadDeviceToken'):
                c.execute('UPDATE bininga_push_devices SET active=FALSE WHERE id=%s', (device,))
        c.execute('SELECT status,COUNT(*) FROM bininga_push_deliveries WHERE message_id=%s GROUP BY status', (ident,))
        counts = dict(c.fetchall())
        result = {key: counts.get(key, 0) for key in ('accepted','rejected','unknown','skipped')}
        result['pending'] = counts.get('pending',0) + counts.get('sending',0)
        result['total'] = sum(counts.values())
        c.execute('UPDATE bininga_push_messages SET status=%s,result=%s WHERE id=%s',
            ('queued' if result['pending'] else 'complete', json.dumps(result), ident))
    return result
