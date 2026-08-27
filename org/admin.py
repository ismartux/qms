from django.contrib import admin
from org.models import (
    Company,
    Plant,
    Floor,
    Shop,
    Line,
    Station,
    Product,
    Department,
    FloorTLAssignment,
    ShopPQEAssignment,
    IPQCMapping,
)


@admin.register(Company)
class CompanyAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "is_active")
    list_filter = ("is_active",)
    search_fields = ("code", "name")


@admin.register(Plant)
class PlantAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "company", "timezone", "is_active")
    list_filter = ("company", "is_active")
    search_fields = ("code", "name")


@admin.register(Floor)
class FloorAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "plant", "is_active")
    list_filter = ("plant", "is_active")
    search_fields = ("code", "name")


@admin.register(Shop)
class ShopAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "plant", "is_active")
    list_filter = ("plant", "is_active")
    search_fields = ("code", "name")


@admin.register(Line)
class LineAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "shop", "floor", "is_active")
    list_filter = ("shop", "floor", "is_active")
    search_fields = ("code", "name")


@admin.register(Station)
class StationAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "line", "is_active")
    list_filter = ("line", "is_active")
    search_fields = ("code", "name")


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "category", "position", "brand", "plant", "is_active")
    list_filter = ("plant", "category", "is_active")
    search_fields = ("code", "name", "category", "position", "brand")


@admin.register(Department)
class DepartmentAdmin(admin.ModelAdmin):
    list_display = ("name", "code", "plant", "is_active")
    list_filter = ("plant", "is_active")
    search_fields = ("name", "code")


@admin.register(FloorTLAssignment)
class FloorTLAssignmentAdmin(admin.ModelAdmin):
    list_display = ("user", "floor", "shift", "is_active", "assigned_by", "created_at")
    list_filter = ("floor__plant", "floor", "shift", "is_active")
    search_fields = ("user__username", "user__first_name", "user__last_name", "floor__name")


@admin.register(ShopPQEAssignment)
class ShopPQEAssignmentAdmin(admin.ModelAdmin):
    list_display = ("user", "shop", "is_active", "assigned_by", "created_at")
    list_filter = ("shop__plant", "shop", "is_active")
    search_fields = ("user__username", "user__first_name", "user__last_name", "shop__name")


@admin.register(IPQCMapping)
class IPQCMappingAdmin(admin.ModelAdmin):
    list_display = ("user", "plant", "floor", "shop", "shift", "is_active", "created_at")
    list_filter = ("plant", "floor", "shop", "shift", "is_active")
    search_fields = ("user__username", "user__first_name", "user__last_name")
    filter_horizontal = ("lines",)