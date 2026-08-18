from django.contrib import admin

from forms_engine.models import (
    ChecklistTemplate,
    ChecklistVersion,
    ChecklistSection,
    ChecklistItem,
    ChecklistRule,
    ChecklistItemOption,
    TemplateRole,
    ChecklistApprovalStep,
)


# =====================================================
# INLINE DEFINITIONS
# =====================================================

class ChecklistRuleInline(admin.TabularInline):
    model = ChecklistRule
    extra = 0


class ChecklistItemOptionInline(admin.TabularInline):
    """
    Dropdown options inline INSIDE ChecklistItem admin
    """
    model = ChecklistItemOption
    extra = 1
    ordering = ("order",)


class ChecklistItemInline(admin.TabularInline):
    model = ChecklistItem
    extra = 0


class ChecklistSectionInline(admin.TabularInline):
    model = ChecklistSection
    extra = 0


class ChecklistVersionInline(admin.TabularInline):
    model = ChecklistVersion
    extra = 0


class TemplateRoleInline(admin.TabularInline):
    model = TemplateRole
    extra = 1


# =====================================================
# TEMPLATE ADMIN
# =====================================================

class ChecklistApprovalStepInline(admin.TabularInline):
    model = ChecklistApprovalStep
    extra = 1
    ordering = ("order",)
    fields = ("category", "order", "is_required")


@admin.register(ChecklistTemplate)
class ChecklistTemplateAdmin(admin.ModelAdmin):

    list_display = (
        "code",
        "name",
        "department",
        "is_active",
        "bitable_table_id",
        "created_at",
    )

    list_filter = (
        "department",
        "is_active",
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

    inlines = [
        ChecklistApprovalStepInline,   # 🔑 THIS replaces approval_flow
    ]

    fieldsets = (

        ("Template Info", {
            "fields": (
                "code",
                "name",
                "description",
                "is_active",
            )
        }),

        ("Ownership & Applicability", {
            "fields": (
                "department",
                "plants",
                "products",
                "shops",
            ),
            "description": (
                "Department is mandatory. "
                "Leave Products or Shops empty to apply universally."
            )
        }),

        ("Approval Workflow", {
            "description": (
                "Define approval steps below. "
                "Order controls sequence. "
                "Uncheck 'required' to make a step optional."
            ),
            "fields": (),   # 👈 approval is defined via inline
        }),

        ("Bitable Integration", {
            "fields": (
                "bitable_app_token",
                "bitable_table_id",
            ),
        }),
    )

# =====================================================
# VERSION ADMIN
# =====================================================

@admin.register(ChecklistVersion)
class ChecklistVersionAdmin(admin.ModelAdmin):

    list_display = (
        "id",
        "template",
        "version_number",
        "is_active",
        "is_published",
        "created_at",
    )

    list_filter = (
        "template",
        "is_active",
        "is_published",
    )

    ordering = (
        "template",
        "version_number",
    )


# =====================================================
# SECTION ADMIN
# =====================================================

@admin.register(ChecklistSection)
class ChecklistSectionAdmin(admin.ModelAdmin):

    list_display = (
        "title",
        "version",
        "order",
    )

    ordering = (
        "version",
        "order",
    )

    inlines = [
        ChecklistItemInline,
    ]


# =====================================================
# ITEM ADMIN
# =====================================================

@admin.register(ChecklistItem)
class ChecklistItemAdmin(admin.ModelAdmin):

    list_display = (
        "label",
        "item_type",
        "required",
        "severity_weight",
        "order",
        "section",
    )

    list_filter = (
        "item_type",
        "required",
    )

    ordering = (
        "section",
        "order",
    )

    inlines = [
        ChecklistRuleInline,
        ChecklistItemOptionInline,
    ]

    def get_inline_instances(self, request, obj=None):
        """
        Show dropdown options ONLY when item_type == DROPDOWN
        """
        inlines = super().get_inline_instances(request, obj)

        if obj and obj.item_type != "DROPDOWN":
            inlines = [
                inline for inline in inlines
                if not isinstance(inline, ChecklistItemOptionInline)
            ]

        return inlines


# =====================================================
# RULE ADMIN
# =====================================================

@admin.register(ChecklistRule)
class ChecklistRuleAdmin(admin.ModelAdmin):

    list_display = (
        "item",
        "rule_type",
        "condition_value",
    )

    list_filter = (
        "rule_type",
    )

    search_fields = (
        "item__label",
    )

    def save_model(self, request, obj, form, change):
        obj.condition_value = obj.condition_value.strip().upper()
        super().save_model(request, obj, form, change)


# =====================================================
# DROPDOWN OPTION ADMIN
# =====================================================

@admin.register(ChecklistItemOption)
class ChecklistItemOptionAdmin(admin.ModelAdmin):

    list_display = (
        "item",
        "label",
        "value",
        "order",
    )

    ordering = (
        "item",
        "order",
    )


@admin.register(ChecklistApprovalStep)
class ChecklistApprovalStepAdmin(admin.ModelAdmin):
    list_display = ("template", "category", "order", "is_required")
    list_filter = ("category", "is_required")
    search_fields = ("template__code", "template__name")
    ordering = ("template", "order")


@admin.register(TemplateRole)
class TemplateRoleAdmin(admin.ModelAdmin):
    list_display = ("template", "role")
    list_filter = ("role",)
    search_fields = ("template__code", "template__name", "role__name")