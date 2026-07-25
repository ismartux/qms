from django.contrib import admin
from .models import LarkConfig, BitableConfig

@admin.register(LarkConfig)
class LarkConfigAdmin(admin.ModelAdmin):
    list_display = ("name", "webhook_url")
    search_fields = ("name", "webhook_url")

@admin.register(BitableConfig)
class BitableConfigAdmin(admin.ModelAdmin):
    list_display = ("name", "app_token", "table_id")
    search_fields = ("name", "app_token", "table_id")
