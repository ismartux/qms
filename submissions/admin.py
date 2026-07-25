from django.contrib import admin

from submissions.models import (
    # Core
    Submission,
    SubmissionResponse,
    SubmissionAttachment,
    SubmissionSyncLog,
    WorkContext,
    SubmissionApproval,

    # 🔥 Dynamic Forms
    DynamicFormSubmission,
    DynamicFormSubmissionValue,
)


# =========================================================
# CHECKLIST SUBMISSION RESPONSE INLINE
# =========================================================

class SubmissionResponseInline(admin.TabularInline):
    model = SubmissionResponse
    extra = 0
    readonly_fields = [f.name for f in SubmissionResponse._meta.fields]
    can_delete = False


# =========================================================
# CHECKLIST SUBMISSION SYNC LOG INLINE
# =========================================================

class SubmissionSyncLogInline(admin.TabularInline):
    model = SubmissionSyncLog
    extra = 0
    readonly_fields = [f.name for f in SubmissionSyncLog._meta.fields]
    can_delete = False


# =========================================================
# CHECKLIST ATTACHMENTS
# =========================================================

@admin.register(SubmissionAttachment)
class SubmissionAttachmentAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "submission",
        "checklist_item",
        "attachment_type",
        "file",
        "uploaded_at",
    )

    readonly_fields = (
        "uploaded_at",
    )

    list_filter = (
        "attachment_type",
        "uploaded_at",
    )


# =========================================================
# WORK CONTEXT (TENANT SAFE)
# =========================================================

@admin.register(WorkContext)
class WorkContextAdmin(admin.ModelAdmin):
    list_display = (
        "plant",
        "shop",
        "line",
        "product",
        "shift",
        "work_date",
        "process_type",
        "is_active",
        "created_by",
        "created_at",
    )

    list_filter = (
        "plant",
        "process_type",
        "shift",
        "work_date",
        "is_active",
    )

    search_fields = (
        "line__code",
        "product__name",
    )

    readonly_fields = (
        "created_at",
    )


# =========================================================
# CHECKLIST SUBMISSION ADMIN
# =========================================================

@admin.register(Submission)
class SubmissionAdmin(admin.ModelAdmin):
    list_display = (
        "submission_id",
        "template_version",
        "workflow_state",
        "severity_score",
        "submitted_by",
        "submitted_at",
        "created_at",
    )

    list_filter = (
        "workflow_state",
        "template_version",
        "submitted_at",
    )

    search_fields = (
        "submission_id",
        "submitted_by__username",
    )

    inlines = [
        SubmissionResponseInline,
        SubmissionSyncLogInline,
    ]

    readonly_fields = [f.name for f in Submission._meta.fields]

    def has_change_permission(self, request, obj=None):
        # 🔐 Immutable once not draft
        if obj and obj.workflow_state != "DRAFT":
            return False
        return super().has_change_permission(request, obj)

    def has_delete_permission(self, request, obj=None):
        # 🔐 Audit safety
        return False


# =========================================================
# SUBMISSION APPROVALS (MULTI-ROLE, READ-ONLY)
# =========================================================

@admin.register(SubmissionApproval)
class SubmissionApprovalAdmin(admin.ModelAdmin):

    list_display = (
        "submission",
        "category",
        "status",
        "approver_name",
        "plant",
        "line",
        "product",
        "created_at",
    )

    readonly_fields = (
        "submission",
        "category",
        "status",
        "approver_name",
        "rejection_reason",
        "created_at",
    )

    list_filter = (
        "category",
        "status",
        "created_at",
    )

    search_fields = (
        "submission__submission_id",
        "approver_name",
    )

    def plant(self, obj):
        return obj.submission.plant
    plant.short_description = "Plant"

    def line(self, obj):
        return obj.submission.line
    line.short_description = "Line"

    def product(self, obj):
        return obj.submission.product
    product.short_description = "Product"

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


# =========================================================
# 🔥 DYNAMIC FORM SUBMISSION VALUES INLINE
# =========================================================

class DynamicFormSubmissionValueInline(admin.TabularInline):
    model = DynamicFormSubmissionValue
    extra = 0
    can_delete = False
    readonly_fields = (
        "field",
        "value",
        "remark",
        "is_non_conformance",
    )


# =========================================================
# 🔥 DYNAMIC FORM SUBMISSION ADMIN
# =========================================================

@admin.register(DynamicFormSubmission)
class DynamicFormSubmissionAdmin(admin.ModelAdmin):

    list_display = (
        "submission_id",
        "template_version",
        "workflow_state",
        "submitted_by",
        "submitted_at",
        "created_at",
    )

    list_filter = (
        "workflow_state",
        "template_version",
        "submitted_at",
    )

    search_fields = (
        "submission_id",
        "submitted_by__username",
        "template_version__template__code",
    )

    readonly_fields = [f.name for f in DynamicFormSubmission._meta.fields]

    inlines = [
        DynamicFormSubmissionValueInline,
    ]

    def has_change_permission(self, request, obj=None):
        # 🔐 Immutable once not draft
        if obj and obj.workflow_state != "DRAFT":
            return False
        return super().has_change_permission(request, obj)

    def has_delete_permission(self, request, obj=None):
        return False


# =========================================================
# 🔥 DYNAMIC FORM VALUE ADMIN (DEBUG / SEARCH ONLY)
# =========================================================

@admin.register(DynamicFormSubmissionValue)
class DynamicFormSubmissionValueAdmin(admin.ModelAdmin):

    list_display = (
        "submission",
        "field",
        "value",
        "is_non_conformance",
    )

    list_filter = (
        "is_non_conformance",
        "field",
    )

    search_fields = (
        "submission__submission_id",
        "field__label",
        "value",
    )

    ordering = ("submission",)

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False