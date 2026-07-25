from django.contrib import admin
from .models import FormSchedule, ScheduledInstance, SchedulerControl


# ==========================================================
# FormSchedule Admin
# ==========================================================

@admin.register(FormSchedule)
class FormScheduleAdmin(admin.ModelAdmin):

    list_display = (
        "template",
        "schedule_type",
        "interval_minutes",
        "times_per_shift",
        "daily_time",
        "is_active",
        "created_at",
    )

    list_filter = (
        "schedule_type",
        "is_active",
        "created_at",
    )

    search_fields = (
        "template__name",
    )

    readonly_fields = ("created_at",)

    fieldsets = (
        ("Basic Info", {
            "fields": ("template", "schedule_type", "is_active")
        }),
        ("Interval Settings", {
            "fields": ("interval_minutes",),
        }),
        ("Shift Limit Settings", {
            "fields": ("times_per_shift",),
        }),
        ("Daily Settings", {
            "fields": ("daily_time",),
        }),
        ("System Info", {
            "fields": ("created_at",),
        }),
    )


# ==========================================================
# ScheduledInstance Admin
# ==========================================================

@admin.register(ScheduledInstance)
class ScheduledInstanceAdmin(admin.ModelAdmin):

    list_display = (
        "schedule",
        "expected_at",
        "is_completed",
        "created_submission_id",
        "created_at",
    )

    list_filter = (
        "is_completed",
        "expected_at",
    )

    search_fields = (
        "schedule__template__name",
    )

    readonly_fields = (
        "created_at",
        "created_submission_id",
    )

    ordering = ("-expected_at",)


# ==========================================================
# SchedulerControl Admin
# ==========================================================

@admin.register(SchedulerControl)
class SchedulerControlAdmin(admin.ModelAdmin):

    list_display = ("last_run",)
    readonly_fields = ("last_run",)

    def has_add_permission(self, request):
        # Prevent creating multiple control rows
        return not SchedulerControl.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False