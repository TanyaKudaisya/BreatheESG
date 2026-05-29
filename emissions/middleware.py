"""
Tenant middleware for multi-tenant request isolation.

Captures the authenticated user's tenant_id at the start of each request
and stores it in thread-local storage so that TenantManager can
automatically scope all database queries to the correct tenant.

The tenant context is always cleared on response/exception to prevent
data leakage between requests on the same thread.

Requirements: 1.2, 1.4
"""

import logging
from typing import Callable

from django.http import HttpRequest, HttpResponse

from emissions.tenant_context import clear_current_tenant, set_current_tenant

logger = logging.getLogger(__name__)


class TenantMiddleware:
    """
    Django middleware that sets the current tenant context for each request.

    Must be placed in MIDDLEWARE after
    ``django.contrib.auth.middleware.AuthenticationMiddleware`` so that
    ``request.user`` is already populated when this middleware runs.

    Lifecycle:
        1. ``__call__`` is invoked for every request.
        2. If the user is authenticated and has a ``tenant_id`` attribute,
           the tenant context is set via ``set_current_tenant()``.
        3. The request is passed to the next middleware / view.
        4. Regardless of success or exception, ``clear_current_tenant()``
           is called in the ``finally`` block to prevent context leakage.
    """

    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]) -> None:
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        # Set tenant context before the view runs
        self._set_tenant_from_request(request)

        try:
            response = self.get_response(request)
        finally:
            # Always clear — prevents leakage between requests on the same
            # thread (critical for gunicorn/uWSGI thread-pool workers).
            clear_current_tenant()

        return response

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _set_tenant_from_request(request: HttpRequest) -> None:
        """
        Read tenant_id from the authenticated user and store it in
        thread-local context.

        Silently skips if:
        - The user is not authenticated (anonymous request).
        - The user model does not have a ``tenant_id`` attribute (e.g.,
          Django's built-in User during tests or before task 1.2 models
          are applied).
        """
        user = getattr(request, "user", None)

        if user is None or not user.is_authenticated:
            # Anonymous request — no tenant context
            set_current_tenant(None)
            return

        tenant_id = getattr(user, "tenant_id", None)

        if tenant_id is None:
            logger.debug(
                "Authenticated user %s has no tenant_id — "
                "tenant context will not be set.",
                getattr(user, "pk", "unknown"),
            )
            set_current_tenant(None)
            return

        set_current_tenant(tenant_id)
        logger.debug(
            "Tenant context set to %s for user %s.",
            tenant_id,
            getattr(user, "pk", "unknown"),
        )
