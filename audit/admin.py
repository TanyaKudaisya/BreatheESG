from django.contrib import admin

from .models import AuditEvent


@admin.register(AuditEvent)
class AuditEventAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "event_type",
        "emission_record_id",
        "tenant_id",
        "user_id",
        "field_name",
        "timestamp",
    )
    list_filter = ("event_type",)
    search_fields = ("field_name",)
    readonly_fields = (
        "id",
        "emission_record_id",
        "tenant_id",
        "user_id",
        "event_type",
        "timestamp",
        "field_name",
        "old_value",
        "new_value",
        "metadata",
    )
    date_hierarchy = "timestamp"

    def has_add_permission(self, request):
        """Audit events are created programmatically only."""
        return False

    def has_change_permission(self, request, obj=None):
        """Audit events are immutable."""
        return False

    def has_delete_permission(self, request, obj=None):
        """Audit events cannot be deleted."""
        return False
