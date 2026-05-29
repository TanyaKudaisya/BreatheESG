from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from .models import (
    DataQualityFlag,
    EmissionRecord,
    MonthlyAllocation,
    Tenant,
    User,
)


@admin.register(Tenant)
class TenantAdmin(admin.ModelAdmin):
    list_display = ("name", "code", "created_at")
    search_fields = ("name", "code")
    ordering = ("name",)


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = ("username", "email", "tenant", "role", "is_staff", "is_active")
    list_filter = ("role", "tenant", "is_staff", "is_active")
    search_fields = ("username", "email", "first_name", "last_name")
    fieldsets = BaseUserAdmin.fieldsets + (
        ("Breathe ESG", {"fields": ("tenant", "role")}),
    )
    add_fieldsets = BaseUserAdmin.add_fieldsets + (
        ("Breathe ESG", {"fields": ("tenant", "role")}),
    )


@admin.register(EmissionRecord)
class EmissionRecordAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "tenant",
        "source_system",
        "transaction_date",
        "location",
        "fuel_type",
        "scope",
        "approval_status",
        "is_locked",
        "ingestion_timestamp",
    )
    list_filter = ("source_system", "scope", "approval_status", "is_locked", "tenant")
    search_fields = ("location", "fuel_type", "ebeln", "account_number", "report_id")
    readonly_fields = ("id", "ingestion_timestamp", "raw_data")
    date_hierarchy = "transaction_date"


@admin.register(DataQualityFlag)
class DataQualityFlagAdmin(admin.ModelAdmin):
    list_display = (
        "emission_record",
        "flag_type",
        "severity",
        "field_name",
        "is_resolved",
        "resolved_at",
    )
    list_filter = ("flag_type", "severity", "is_resolved")
    search_fields = ("message", "field_name")
    readonly_fields = ("id",)


@admin.register(MonthlyAllocation)
class MonthlyAllocationAdmin(admin.ModelAdmin):
    list_display = ("emission_record", "year", "month", "allocated_quantity", "unit")
    list_filter = ("year", "month")
    readonly_fields = ("id",)
