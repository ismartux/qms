from django.contrib import admin
from django.forms import BaseInlineFormSet
from django.core.exceptions import ValidationError

from dynamic_forms.models import (
    DynamicFormTemplate,
    DynamicFormVersion,
    DynamicFormField,
    DynamicTemplateRole,
    DynamicFormStandardRule,
    TemplateApprovalStep,
)

# =========================================================
# INLINE HELPERS
# =========================================================

class PublishedVersionProtectionFormSet(BaseInlineFormSet):
    """
    Prevent edits to objects belonging to published versions
    """

    def clean(self):
        super().clean()

        for form in self.forms:
            if not form.instance.pk:
                continue

            # Covers DynamicFormField, DynamicFormStandardRule, etc.
            if hasattr(form.instance, "version"):
                if form.instance.version.is_published and form.has_changed():
                    raise ValidationError(
                        "Published versions are locked and cannot be modified."
                    )


# =========================================================
# FORM FIELD INLINE (READ-ONLY SNAPSHOT VIEW)
# =========================================================

class DynamicFormFieldInline(admin.TabularInline):
    model = DynamicFormField
    extra = 0
    ordering = ("order",)
    formset = PublishedVersionProtectionFormSet

    fields = (
        "order",
        "label",
        "field_kind",
        "data_type",
        "bitable_column_id",
        "required",
    )

    readonly_fields = fields
    can_delete = False
    show_change_link = True


# =========================================================
# STANDARD RULE INLINE (READ-ONLY FOR PUBLISHED)
# =========================================================

class DynamicFormStandardRuleInline(admin.TabularInline):
    model = DynamicFormStandardRule
    extra = 0
    formset = PublishedVersionProtectionFormSet

    fields = (
        "target_field",
        "value_source",
        "manual_value",
        "bitable_column_id",
        "operator",
    )

    show_change_link = True


# =========================================================
# VERSION ADMIN
# =========================================================

@admin.register(DynamicFormVersion)
class DynamicFormVersionAdmin(admin.ModelAdmin):
    list_display = (
        "template",
        "version_number",
        "is_active",
        "is_published",
        "created_at",
    )

    list_filter = (
        "is_active",
        "is_published",
        "template",
    )

    search_fields = (
        "template__code",
        "template__name",
    )

    inlines = [
        DynamicFormFieldInline,
        DynamicFormStandardRuleInline,
    ]

    ordering = ("-version_number",)

    def has_delete_permission(self, request, obj=None):
        if obj and obj.is_published:
            return False
        return super().has_delete_permission(request, obj)

    def has_change_permission(self, request, obj=None):
        if obj and obj.is_published:
            return False
        return super().has_change_permission(request, obj)


# =========================================================
# ROLE ASSIGNMENT INLINE
# =========================================================

class DynamicTemplateRoleInline(admin.TabularInline):
    model = DynamicTemplateRole
    extra = 0

    fields = (
        "role",
        "requires_work_context",
    )


# =========================================================
# TEMPLATE ADMIN
# =========================================================

class TemplateApprovalStepInline(admin.TabularInline):
    model = TemplateApprovalStep
    extra = 0
    min_num = 0
    ordering = ("order",)
    fields = ("category", "order", "is_required")

@admin.register(DynamicFormTemplate)
class DynamicFormTemplateAdmin(admin.ModelAdmin):
    list_display = (
        "code",
        "name",
        "department",
        "submission_mode",
        "is_active",
        "is_archived",
        "created_at",
    )

    list_filter = (
        "submission_mode",
        "is_active",
        "is_archived",
        "department",
        "plants",
    )

    search_fields = (
        "code",
        "name",
    )

    filter_horizontal = (
        "plants",
        "products",
        "shops",
    )

    fieldsets = (
        (
            "Basic Information",
            {
                "fields": (
                    "code",
                    "name",
                    "description",
                    "department",
                )
            },
        ),
        (
            "Submission Behavior",
            {
                "fields": (
                    "submission_mode",
                ),
                "description": (
                    "Controls how submission data is written to Bitable. "
                    "Do not change this after submissions exist."
                ),
            },
        ),
        (
            "Applicability",
            {
                "fields": (
                    "plants",
                    "products",
                    "shops",
                )
            },
        ),
        (
            "Bitable Configuration",
            {
                "fields": (
                    "source_bitable_app_token",
                    "source_bitable_table_id",
                    "submission_bitable_app_token",
                    "submission_bitable_table_id",
                )
            },
        ),
        (
            "Status",
            {
                "fields": (
                    "is_active",
                    "is_archived",
                )
            },
        ),
    )

    inlines = [
        TemplateApprovalStepInline,   # 🔑 NEW
        DynamicTemplateRoleInline,
    ]

    def has_delete_permission(self, request, obj=None):
        if obj and obj.versions.filter(is_published=True).exists():
            return False
        return super().has_delete_permission(request, obj)
    

@admin.register(TemplateApprovalStep)
class TemplateApprovalStepAdmin(admin.ModelAdmin):
    list_display = (
        "template",
        "category",
        "order",
        "is_required",
    )
    list_filter = (
        "category",
        "is_required",
    )
    ordering = ("template", "order")
    search_fields = (
        "template__code",
        "category__code",
    )
    
    
# =========================================================
# FORM FIELD ADMIN (DEBUG / SEARCH ONLY)
# =========================================================

@admin.register(DynamicFormField)
class DynamicFormFieldAdmin(admin.ModelAdmin):
    list_display = (
        "label",
        "version",
        "field_kind",
        "data_type",
        "bitable_column_id",
        "required",
        "order",
    )

    list_filter = (
        "field_kind",
        "data_type",
        "version__template",
    )

    search_fields = (
        "label",
        "bitable_column_id",
    )

    ordering = ("version", "order")

    def has_add_permission(self, request):
        # ❌ Fields must be created via Builder
        return False


# =========================================================
# STANDARD RULE ADMIN (DEBUG / AUDIT)
# =========================================================

@admin.register(DynamicFormStandardRule)
class DynamicFormStandardRuleAdmin(admin.ModelAdmin):
    list_display = (
        "target_field",
        "version",
        "value_source",
        "operator",
        "created_at",
    )

    list_filter = (
        "value_source",
        "operator",
        "version__template",
    )

    search_fields = (
        "target_field__label",
        "manual_value",
        "bitable_column_id",
    )

    ordering = ("-created_at",)

    def has_add_permission(self, request):
        # Created via Builder / Version logic only
        return False