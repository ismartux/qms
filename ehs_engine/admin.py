from django.contrib import admin
from django.core.exceptions import ValidationError

from .models import (
    EHSFormTemplate,
    EHSFormVersion,
    EHSSection,
    EHSItem,
    EHSItemOption,
    EHSRule,
    EHSSubmission,
    EHSResponse,
    RiskAssessment,
    EHSWorkflowTemplate,
    WorkflowStep,
    WorkflowActionLog,
    CAPA,
)


# =========================================================
# FORM BUILDER ADMIN
# =========================================================

class EHSItemOptionInline(admin.TabularInline):
    model = EHSItemOption
    extra = 0


class EHSRuleInline(admin.TabularInline):
    model = EHSRule
    extra = 0


class EHSItemInline(admin.TabularInline):
    model = EHSItem
    extra = 0
    show_change_link = True


class EHSSectionInline(admin.TabularInline):
    model = EHSSection
    extra = 0
    show_change_link = True


# ---------------------------------------------------------
# TEMPLATE ADMIN
# ---------------------------------------------------------

@admin.register(EHSFormTemplate)
class EHSFormTemplateAdmin(admin.ModelAdmin):
    list_display = (
        "code",
        "name",
        "department",
        "is_active",
        "is_archived",
        "created_at",
    )
    list_filter = ("is_active", "is_archived", "department", "plants")
    search_fields = ("code", "name")
    filter_horizontal = ("plants",)
    readonly_fields = ("department",)

    def has_change_permission(self, request, obj=None):
        if obj and obj.versions.filter(is_published=True).exists():
            return False
        return super().has_change_permission(request, obj)


# ---------------------------------------------------------
# VERSION ADMIN
# ---------------------------------------------------------

@admin.register(EHSFormVersion)
class EHSFormVersionAdmin(admin.ModelAdmin):
    list_display = (
        "template",
        "version_number",
        "is_active",
        "is_published",
        "created_at",
    )
    list_filter = ("is_active", "is_published")
    inlines = [EHSSectionInline]


# ---------------------------------------------------------
# SECTION ADMIN
# ---------------------------------------------------------

@admin.register(EHSSection)
class EHSSectionAdmin(admin.ModelAdmin):
    list_display = ("title", "version", "order")
    list_filter = ("version",)
    inlines = [EHSItemInline]


# ---------------------------------------------------------
# ITEM ADMIN
# ---------------------------------------------------------

@admin.register(EHSItem)
class EHSItemAdmin(admin.ModelAdmin):
    list_display = (
        "label",
        "section",
        "item_type",
        "required",
        "severity_weight",
        "require_photo_on_no",
        "require_remark_on_no",
        "escalate_on_no",
        "order",
    )
    list_filter = (
        "item_type",
        "required",
        "require_photo_on_no",
        "require_remark_on_no",
        "escalate_on_no",
    )
    search_fields = ("label", "item_id")
    inlines = [EHSItemOptionInline, EHSRuleInline]


# =========================================================
# SUBMISSION ADMIN
# =========================================================

class EHSResponseInline(admin.TabularInline):
    model = EHSResponse
    extra = 0
    can_delete = False
    readonly_fields = (
        "item",
        "value",
        "remark",
        "photo",
        "created_at",
    )

    def has_add_permission(self, request, obj=None):
        return False


class RiskAssessmentInline(admin.StackedInline):
    model = RiskAssessment
    extra = 0
    can_delete = False
    readonly_fields = ("likelihood", "severity", "score")

    def has_add_permission(self, request, obj=None):
        return False


class WorkflowActionLogInline(admin.TabularInline):
    model = WorkflowActionLog
    extra = 0
    can_delete = False
    readonly_fields = (
        "action",
        "performed_by",
        "comment",
        "created_at",
    )

    def has_add_permission(self, request, obj=None):
        return False


class CAPAInline(admin.TabularInline):
    model = CAPA
    extra = 0


@admin.register(EHSSubmission)
class EHSSubmissionAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "version",
        "plant",
        "reported_by",
        "status",
        "risk_score",
        "risk_category",
        "created_at",
    )
    list_filter = ("status", "risk_category", "plant")
    search_fields = ("id", "reported_by__username")
    readonly_fields = (
        "risk_score",
        "risk_category",
        "created_at",
    )
    inlines = [
        EHSResponseInline,
        RiskAssessmentInline,
        WorkflowActionLogInline,
        CAPAInline,
    ]

    def has_change_permission(self, request, obj=None):
        if obj and obj.status != "DRAFT":
            return False
        return super().has_change_permission(request, obj)


# =========================================================
# WORKFLOW ADMIN
# =========================================================

class WorkflowStepInline(admin.TabularInline):
    model = WorkflowStep
    extra = 0


@admin.register(EHSWorkflowTemplate)
class EHSWorkflowTemplateAdmin(admin.ModelAdmin):
    list_display = ("name", "template")
    inlines = [WorkflowStepInline]


# =========================================================
# CAPA ADMIN (Standalone View)
# =========================================================

@admin.register(CAPA)
class CAPAAdmin(admin.ModelAdmin):
    list_display = (
        "submission",
        "responsible_person",
        "target_date",
        "status",
    )
    list_filter = ("status", "target_date")
    search_fields = (
        "submission__id",
        "responsible_person__username",
    )