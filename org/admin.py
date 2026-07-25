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
    list_display = ("code", "name")
    search_fields = ("code", "name")


@admin.register(Plant)
class PlantAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "company", "timezone")
    list_filter = ("company",)
    search_fields = ("code", "name")


@admin.register(Shop)
class ShopAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "plant")
    list_filter = ("plant",)
    search_fields = ("code", "name")


@admin.register(Line)
class LineAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "shop")
    list_filter = ("shop",)
    search_fields = ("code", "name")


@admin.register(Station)
class StationAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "line")
    list_filter = ("line",)
    search_fields = ("code", "name")


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "category", "position", "brand", "plant")
    search_fields = ("code", "name", "category", "position", "brand", "plant")
    
    
@admin.register(Department)
class DepartmentAdmin(admin.ModelAdmin):
    list_display = ("name", "code", "plant")
    list_filter = ("plant",)
    search_fields = ("name", "code")