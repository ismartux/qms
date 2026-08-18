from django.contrib import admin
from core.workflow.models import Approval


@admin.register(Approval)
class ApprovalAdmin(admin.ModelAdmin):
    list_display = (
        "approval_id",
        "object_type",
        "object_id",
        "requested_by",
        "approved_by",
        "status",
        "created_at",
        "decided_at",
    )

    list_filter = (
        "status",
        "object_type",
        "created_at",
        "decided_at",
    )

    search_fields = (
        "approval_id",
        "object_type",
        "object_id",
        "requested_by__username",
        "approved_by__username",
        "remarks",
    )

    readonly_fields = (
        "approval_id",
        "created_at",
    )

    ordering = ("-created_at",)
