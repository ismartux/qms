from django.contrib import admin
from integrations.models import (
    IntegrationTarget,
    IntegrationTemplateMapping,
    IntegrationFieldMapping,
)


class IntegrationFieldMappingInline(admin.TabularInline):
    model = IntegrationFieldMapping
    extra = 0


@admin.register(IntegrationTemplateMapping)
class IntegrationTemplateMappingAdmin(admin.ModelAdmin):
    list_display = ("template", "target", "external_table_id", "enabled")
    inlines = [IntegrationFieldMappingInline]


@admin.register(IntegrationTarget)
class IntegrationTargetAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "is_active")
    search_fields = ("code", "name")


@admin.register(IntegrationFieldMapping)
class IntegrationFieldMappingAdmin(admin.ModelAdmin):
    list_display = ("template_mapping", "item_id", "external_field", "transform")
    search_fields = ("template_mapping__template__code", "item_id", "external_field")