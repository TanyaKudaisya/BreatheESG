"""
Tenant-aware QuerySet and Manager for multi-tenant data isolation.

All models that store per-tenant data should use ``TenantManager`` as
their default manager.  When a tenant context is active (i.e., a request
is being processed by an authenticated user), ``get_queryset()`` will
automatically filter results to the current tenant.

When no tenant context is set — during management commands, migrations,
shell sessions, or background tasks — the full, unfiltered queryset is
returned so that administrative operations still work correctly.

Requirements: 1.1, 1.2, 1.3, 1.4
"""

import uuid
from typing import Optional

from django.db import models
from django.db.models import QuerySet

from emissions.tenant_context import get_current_tenant


class TenantQuerySet(QuerySet):
    """
    A QuerySet subclass that adds a ``for_tenant()`` convenience method.

    This allows callers to explicitly scope a queryset to a specific
    tenant without relying on the thread-local context:

        EmissionRecord.objects.for_tenant(tenant_id).filter(scope=1)
    """

    def for_tenant(self, tenant_id: uuid.UUID) -> "TenantQuerySet":
        """
        Return a queryset filtered to the given tenant_id.

        Args:
            tenant_id: The UUID of the tenant to filter by.

        Returns:
            A filtered TenantQuerySet containing only records that
            belong to the specified tenant.
        """
        return self.filter(tenant_id=tenant_id)


class TenantManager(models.Manager):
    """
    A custom Manager that automatically scopes queries to the current tenant.

    Behaviour:
    - When ``get_current_tenant()`` returns a non-None value, all queries
      are automatically filtered to that tenant.
    - When ``get_current_tenant()`` returns None (management commands,
      migrations, unauthenticated contexts), the full queryset is returned.

    Usage on a model::

        class EmissionRecord(models.Model):
            tenant_id = models.UUIDField(...)
            objects = TenantManager()

    Explicit tenant scoping (bypasses thread-local context)::

        EmissionRecord.objects.for_tenant(some_tenant_id).all()
    """

    def get_queryset(self) -> TenantQuerySet:
        """
        Return a TenantQuerySet, automatically filtered by the current
        tenant when a tenant context is active.
        """
        qs = TenantQuerySet(self.model, using=self._db)

        current_tenant: Optional[uuid.UUID] = get_current_tenant()
        if current_tenant is not None:
            qs = qs.filter(tenant_id=current_tenant)

        return qs

    def for_tenant(self, tenant_id: uuid.UUID) -> TenantQuerySet:
        """
        Convenience proxy — returns a queryset explicitly scoped to the
        given tenant_id, bypassing the thread-local context.

        This is useful in service-layer code that receives tenant_id as
        a parameter (e.g., ingestion engine, audit trail store).

        Args:
            tenant_id: The UUID of the tenant to filter by.

        Returns:
            A TenantQuerySet filtered to the specified tenant.
        """
        return TenantQuerySet(self.model, using=self._db).for_tenant(tenant_id)
