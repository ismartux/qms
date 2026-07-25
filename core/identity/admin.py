from django.contrib import admin
from core.identity.models import (
    Role,
    Permission,
    RolePermission,
    ApprovalCategory,
)

# =====================================================
# ROLE ↔ PERMISSION INLINE
# =====================================================
class RolePermissionInline(admin.TabularInline):
    model = RolePermission
    extra = 1


# =====================================================
# ROLE ADMIN
# =====================================================
@admin.register(Role)
class RoleAdmin(admin.ModelAdmin):
    list_display = (
        "code",
        "name",
        "is_active",
        "approval_categories_display",
    )
    search_fields = ("code", "name")
    list_filter = ("is_active", "approval_categories")
    inlines = [RolePermissionInline]
    filter_horizontal = ("approval_categories",)  # 🔑 IMPORTANT

    def approval_categories_display(self, obj):
        return ", ".join(
            obj.approval_categories.values_list("code", flat=True)
        )

    approval_categories_display.short_description = "Approval Categories"


# =====================================================
# PERMISSION ADMIN
# =====================================================
@admin.register(Permission)
class PermissionAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "is_active")
    search_fields = ("code", "name")
    list_filter = ("is_active",)


# =====================================================
# ROLE PERMISSION ADMIN
# =====================================================
@admin.register(RolePermission)
class RolePermissionAdmin(admin.ModelAdmin):
    list_display = ("role", "permission")
    list_filter = ("role", "permission")
    search_fields = ("role__code", "permission__code")


# =====================================================
# APPROVAL CATEGORY ADMIN
# =====================================================
@admin.register(ApprovalCategory)
class ApprovalCategoryAdmin(admin.ModelAdmin):
    list_display = (
        "code",
        "name",
        "is_approver",
        "order",
        "is_active",
    )
    list_filter = ("is_active", "is_approver")
    search_fields = ("code", "name")
    ordering = ("order", "code")