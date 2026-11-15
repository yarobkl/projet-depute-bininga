import http.server
import os
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
assert os.environ.get("BININGA_TEST") == "1"
import server

# Exercise the actual HTTP handlers and storage without notifying the cabinet.
server._send_notif_email_async = lambda *args: None
http.server.ThreadingHTTPServer(("127.0.0.1", 18080), server.BiningaHandler).serve_forever()
