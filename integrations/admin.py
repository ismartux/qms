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