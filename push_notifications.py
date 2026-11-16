"""APNs transport and owner-only notification drafts. Never log device tokens or keys."""
import hashlib
import json
import os
import re
import secrets
import time
import uuid
from urllib.parse import urlparse

TOPIC = 'fr.yaroconsulting.bininga.publicapp'


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
    return conn


def send_apns(token, title, body, message_id):
    import httpx
    import jwt
    key = os.environ.get('BININGA_APNS_PRIVATE_KEY', '')
    if not key:
        raise RuntimeError('Clé APNs non configurée')
    bearer = jwt.encode({'iss': 'UK4UQCQ57G', 'iat': int(time.time())}, key,
                        algorithm='ES256', headers={'kid': 'A2J3Z6G7WJ'})
    with httpx.Client(http2=True, timeout=8) as client:
        response = client.post('https://api.push.apple.com/3/device/' + token,
            headers={'authorization': 'bearer ' + bearer, 'apns-topic': TOPIC,
                     'apns-push-type': 'alert', 'apns-priority': '5',
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
                c.execute('SELECT id FROM bininga_push_devices WHERE active=TRUE ORDER BY updated_at DESC LIMIT 101')
                devices = [r[0] for r in c.fetchall()]
                handler._json({'ok': True, 'configured': bool(os.environ.get('BININGA_APNS_PRIVATE_KEY')),
                    'messages': messages, 'devices': devices}); return True
            action = data.get('action')
            if action == 'draft':
                title, body = validate_message(data)
                ident = str(uuid.uuid4())
                c.execute('INSERT INTO bininga_push_messages(id,title,body) VALUES (%s,%s,%s)', (ident,title,body))
                handler._json({'ok': True, 'id': ident}); return True
            if action != 'send': raise ValueError('Action inconnue')
            if not os.environ.get('BININGA_APNS_PRIVATE_KEY'): raise ValueError('Clé APNs non configurée')
            ident = str(uuid.UUID(str(data.get('id', ''))))
            device = str(data.get('device', ''))
            # First release deliberately sends to one selected, opted-in device. No implicit broadcast.
            c.execute('SELECT token FROM bininga_push_devices WHERE id=%s AND active=TRUE', (device,))
            row = c.fetchone()
            if not row: raise ValueError('Sélectionnez un appareil inscrit et autorisé')
            c.execute("UPDATE bininga_push_messages SET status='sending' WHERE id=%s AND status='draft' RETURNING title,body", (ident,))
            message = c.fetchone()
            if not message: raise ValueError('Brouillon absent ou déjà envoyé')
            try:
                status, reason = send_apns(row[0], *message, ident)
                result = {'accepted': status == 200, 'http_status': status, 'reason': reason}
                state = 'accepted' if status == 200 else 'rejected'
                if status == 410 or reason in ('Unregistered', 'BadDeviceToken'):
                    c.execute('UPDATE bininga_push_devices SET active=FALSE WHERE id=%s', (device,))
            except Exception:
                # No automatic retry after an ambiguous transport failure.
                state, result = 'unknown', {'accepted': False, 'reason': 'TransportIndeterminate'}
            c.execute('UPDATE bininga_push_messages SET status=%s,result=%s WHERE id=%s', (state,json.dumps(result),ident))
            server.audit_log('PUSH_SEND', handler.client_address[0], 'Notification ' + ident + ': ' + state)
            handler._json({'ok': True, 'status': state, 'result': result}); return True
    except (ValueError, UnicodeDecodeError):
        handler._json({'ok': False, 'message': 'Données invalides ou action déjà effectuée'}, 400)
    except Exception:
        handler._json({'ok': False, 'message': 'Service notifications indisponible. Aucun succès confirmé.'}, 503)
    return True
