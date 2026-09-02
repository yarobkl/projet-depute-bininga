"""Central request guard pipeline for BININGA.

The WSGI adapter should translate HTTP, not own business/security policy. This
module keeps the ordered guard chain in one place so adding a new protection
cannot silently create a second, divergent request path.
"""
from __future__ import annotations

from contextlib import contextmanager
from typing import Callable, Iterator, Optional

import admin_access_model
import admin_auth_flow
import admin_contact_integrity
import admin_system_authz
import backup_download
import chatbot_hardening
import editorial_publish_integrity


Guard = Callable[[object, object], object]
LegacyAuthorization = Optional[Callable[[object], bool]]


_GUARDS: tuple[Guard, ...] = (
    admin_system_authz.guard_request,
    admin_access_model.guard_request,
    admin_auth_flow.guard_request,
    admin_contact_integrity.guard_request,
    backup_download.guard_request,
    editorial_publish_integrity.guard_request,
    chatbot_hardening.guard_request,
)


def allow_request(server, handler, legacy_authorization: LegacyAuthorization = None) -> bool:
    """Run every request guard in its authoritative order.

    A guard returning exactly ``False`` has already emitted the response and
    stops the pipeline. Any other return value preserves the legacy convention
    and lets the request continue.
    """
    if legacy_authorization is not None and legacy_authorization(handler) is False:
        return False

    for guard in _GUARDS:
        if guard(server, handler) is False:
            return False
    return True


@contextmanager
def mutation_context(server, handler) -> Iterator[None]:
    """Expose the single mutation integrity context used by dynamic requests."""
    with admin_contact_integrity.mutation_guard(server, handler):
        yield


def process_response(server, handler) -> None:
    """Apply response-only enrichments after the authoritative handler ran."""
    admin_auth_flow.postprocess_response(server, handler)
    admin_access_model.postprocess_response(server, handler)


def guard_names() -> tuple[str, ...]:
    """Stable diagnostic surface used by tests and operational tooling."""
    return tuple(f"{guard.__module__}.{guard.__name__}" for guard in _GUARDS)
