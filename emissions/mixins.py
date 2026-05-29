"""
DRF ViewSet mixin for tenant isolation.

Any ViewSet that handles tenant-scoped data should inherit from
``TenantIsolationMixin`` to ensure that ``get_queryset()`` is always
scoped to the authenticated user's tenant.

Requirements: 1.2, 1.4
"""

import logging

from rest_framework.exceptions import PermissionDenied

logger = logging.getLogger(__name__)


class TenantIsolationMixin:
    """
    Mixin for Django REST Framework ViewSets that enforces tenant isolation.

    Override ``get_queryset()`` in your ViewSet to call
    ``super().get_queryset()`` first, which will apply the tenant filter,
    and then add any additional filters on top.

    Example::

        class EmissionRecordViewSet(TenantIsolationMixin, ModelViewSet):
            serializer_class = EmissionRecordSerializer

            def get_queryset(self):
                qs = super().get_queryset()
                # Additional filters on top of the tenant-scoped queryset
                return qs.filter(approval_status="PENDING")

    Raises:
        PermissionDenied: If the authenticated user has no ``tenant_id``
            attribute or it is None.  This prevents accidental full-table
            scans if the user model is misconfigured.
    """

    def get_queryset(self):
        """
        Return a queryset filtered to the authenticated user's tenant.

        Raises:
            PermissionDenied: If the user has no tenant_id.
        """
        user = self.request.user  # type: ignore[attr-defined]

        tenant_id = getattr(user, "tenant_id", None)
        if not tenant_id:
            logger.warning(
                "User %s attempted to access tenant-scoped data but has no "
                "tenant_id.  Raising PermissionDenied.",
                getattr(user, "pk", "unknown"),
            )
            raise PermissionDenied(
                "Your account is not associated with a tenant. "
                "Please contact your administrator."
            )

        # Delegate to the model's TenantManager.for_tenant() to get a
        # clean, unambiguous queryset scoped to this tenant.
        queryset = super().get_queryset()  # type: ignore[misc]

        # If the base queryset already has a tenant filter (from
        # TenantManager.get_queryset()), this is a no-op.  If not (e.g.,
        # the model uses a plain Manager), we apply the filter explicitly.
        if not queryset.query.where:
            queryset = queryset.filter(tenant_id=tenant_id)

        return queryset
