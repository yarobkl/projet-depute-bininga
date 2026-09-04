"""Central request guard pipeline for BININGA."""
from __future__ import annotations

from contextlib import contextmanager
from typing import Callable, Iterator, Optional

import account_incident_response
import admin_access_model
import admin_auth_flow
import admin_contact_integrity
import admin_system_authz
import backup_download
import chatbot_hardening
import db_health_endpoint
import editorial_publish_integrity
import serverless_backup_history
import serverless_monitor_restart

Guard = Callable[[object, object], object]
LegacyAuthorization = Optional[Callable[[object], bool]]

_GUARDS: tuple[Guard, ...] = (
    db_health_endpoint.guard_request,
    admin_system_authz.guard_request,
    account_incident_response.guard_request,
    admin_access_model.guard_request,
    admin_auth_flow.guard_request,
    admin_contact_integrity.guard_request,
    backup_download.guard_request,
    serverless_backup_history.guard_request,
    editorial_publish_integrity.guard_request,
    chatbot_hardening.guard_request,
    serverless_monitor_restart.guard_request,
)


def allow_request(server, handler, legacy_authorization: LegacyAuthorization = None) -> bool:
    if legacy_authorization is not None and legacy_authorization(handler) is False:
        return False
    for guard in _GUARDS:
        if guard(server, handler) is False:
            return False
    return True


@contextmanager
def mutation_context(server, handler) -> Iterator[None]:
    with admin_contact_integrity.mutation_guard(server, handler):
        yield


def process_response(server, handler) -> None:
    admin_auth_flow.postprocess_response(server, handler)
    admin_access_model.postprocess_response(server, handler)


def guard_names() -> tuple[str, ...]:
    return tuple(f"{guard.__module__}.{guard.__name__}" for guard in _GUARDS)
