"""
Role-based permission classes for the Breathe ESG Data Ingestion System.

These DRF BasePermission subclasses enforce role-based access control on
top of the standard IsAuthenticated check.

Requirements: 13.4
"""

from __future__ import annotations

from rest_framework.permissions import BasePermission


class IsAuditor(BasePermission):
    """
    Allow access only to users with the AUDITOR role.

    Requirements: 13.4
    """

    message = "Only users with the Auditor role can perform this action."

    def has_permission(self, request, view) -> bool:
        return (
            request.user
            and request.user.is_authenticated
            and request.user.role == "AUDITOR"
        )


class IsAdmin(BasePermission):
    """
    Allow access only to users with the ADMIN role.

    Requirements: 13.4
    """

    message = "Only users with the Admin role can perform this action."

    def has_permission(self, request, view) -> bool:
        return (
            request.user
            and request.user.is_authenticated
            and request.user.role == "ADMIN"
        )


class IsAnalystOrAbove(BasePermission):
    """
    Allow access to users with ANALYST, AUDITOR, or ADMIN role.

    Requirements: 13.4
    """

    message = "You must have at least the Analyst role to perform this action."

    _ALLOWED_ROLES = {"ANALYST", "AUDITOR", "ADMIN"}

    def has_permission(self, request, view) -> bool:
        return (
            request.user
            and request.user.is_authenticated
            and request.user.role in self._ALLOWED_ROLES
        )
