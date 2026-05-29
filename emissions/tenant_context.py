"""
Thread-local tenant context storage for multi-tenant isolation.

Each request thread stores its own tenant_id here, allowing the
TenantManager to automatically scope queries without passing tenant_id
explicitly through every function call.

Usage:
    # In middleware (set on request entry):
    set_current_tenant(user.tenant_id)

    # In QuerySet managers (read automatically):
    tenant_id = get_current_tenant()

    # In middleware (clear on request exit):
    clear_current_tenant()
"""

import threading
from typing import Optional
import uuid

_thread_local = threading.local()


def set_current_tenant(tenant_id: Optional[uuid.UUID]) -> None:
    """
    Store the current tenant_id in thread-local storage.

    Called by TenantMiddleware at the start of each request after
    the user has been authenticated.

    Args:
        tenant_id: The UUID of the authenticated user's tenant, or None
                   to clear the context (equivalent to calling
                   clear_current_tenant()).
    """
    _thread_local.tenant_id = tenant_id


def get_current_tenant() -> Optional[uuid.UUID]:
    """
    Retrieve the current tenant_id from thread-local storage.

    Returns None if no tenant context has been set (e.g., during
    management commands, migrations, or unauthenticated requests).

    Returns:
        The current tenant UUID, or None if not set.
    """
    return getattr(_thread_local, "tenant_id", None)


def clear_current_tenant() -> None:
    """
    Remove the tenant_id from thread-local storage.

    Called by TenantMiddleware on response and on exception to prevent
    tenant context from leaking between requests on the same thread
    (important for thread-pool-based WSGI servers like gunicorn).
    """
    _thread_local.tenant_id = None
