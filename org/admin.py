from django.contrib import admin
from org.models import (
    Company,
    Plant,
    Shop,
    Line,
    Station,
    Product,
    Department,
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


@admin.register(Shop)
class ShopAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "plant", "is_active")
    list_filter = ("plant", "is_active")
    search_fields = ("code", "name")


@admin.register(Line)
class LineAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "shop", "is_active")
    list_filter = ("shop", "is_active")
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