"""Pre-import safety hooks for the legacy BININGA server on Vercel.

This module runs before ``server.py`` is imported. It prevents the legacy
module-level bootstrap from generating and printing an administrator password
when production has not explicitly configured ``BININGA_PASS``.
"""

import os
import secrets


if os.environ.get("VERCEL") and not os.environ.get("BININGA_PASS"):
    # Process-local placeholder only. admin_bootstrap_hardening removes the
    # matching synthetic user immediately after server.py finishes importing.
    # The value is never printed and is not a production credential.
    os.environ["BININGA_PASS"] = secrets.token_urlsafe(48)
    os.environ["BININGA_EPHEMERAL_BOOTSTRAP"] = "1"
