from django.contrib import admin
from django.utils.html import format_html
from django.utils import timezone
from capa.models import CAPA


@admin.register(CAPA)
class CAPAAdmin(admin.ModelAdmin):

    # ===============================
    # LIST VIEW
    # ===============================
    list_display = (
        "short_id",
        "template_name",
        "severity",
        "status",
        "rca_role",
        "capa_role",
        "rca_done",
        "capa_done",
        "due_date",
        "overdue_status",
        "created_at",
    )

    list_filter = (
        "status",
        "severity",
        "rca_role",
        "capa_role",
        "due_date",
        "created_at",
    )

    search_fields = (
        "capa_id",
        "title",
        "submission__template_version__template__name",
    )

    ordering = ("-created_at",)

    readonly_fields = (
        "capa_id",
        "created_at",
        "closed_at",
        "rejected_at",
    )

    # ===============================
    # DISPLAY HELPERS
    # ===============================

    def short_id(self, obj):
        return str(obj.capa_id)[:8]
    short_id.short_description = "CAPA ID"

    def template_name(self, obj):
        return obj.submission.template_version.template.name
    template_name.short_description = "Template"

    def rca_done(self, obj):
        if obj.rca_submitted:
            return format_html('<span style="color: green; font-weight: bold;">✔ Done</span>')
        return format_html('<span style="color: #999;">Pending</span>')
    rca_done.short_description = "RCA"

    def capa_done(self, obj):
        if obj.capa_submitted:
            return format_html('<span style="color: green; font-weight: bold;">✔ Done</span>')
        return format_html('<span style="color: #999;">Pending</span>')
    capa_done.short_description = "CAPA"

    def overdue_status(self, obj):
        if obj.is_overdue:
            return format_html('<span style="color: red; font-weight: bold;">Overdue</span>')
        return "-"
    overdue_status.short_description = "Overdue"

    # ===============================
    # FIELD ORGANIZATION
    # ===============================
    fieldsets = (
        ("Basic Info", {
            "fields": (
                "capa_id",
                "submission",
                "title",
                "description",
                "severity",
                "status",
            )
        }),

        ("Assignment", {
            "fields": (
                "rca_role",
                "capa_role",
                "assigned_by",
                "due_date",
            )
        }),

        ("RCA", {
            "fields": (
                "rca_summary",
            )
        }),

        ("CAPA Action", {
            "fields": (
                "capa_plan",
            )
        }),

        ("Rejection", {
            "fields": (
                "rejection_reason",
                "rejected_by",
                "rejected_at",
            )
        }),

        ("Closure", {
            "fields": (
                "closed_at",
            )
        }),

        ("System Info", {
            "fields": (
                "created_at",
            )
        }),
    )
