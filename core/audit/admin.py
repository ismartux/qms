from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth import get_user_model

from core.identity.models import UserScope

User = get_user_model()


# =====================================================
# INLINE: USER SCOPE (ONE PLANT PER USER)
# =====================================================
class UserScopeInline(admin.StackedInline):
    model = UserScope
    extra = 0
    max_num = 1
    can_delete = False
    verbose_name = "Plant Scope"
    verbose_name_plural = "Plant Scope"


# =====================================================
# CUSTOM USER ADMIN
# =====================================================
class CustomUserAdmin(UserAdmin):
    inlines = [UserScopeInline]


# Safely unregister existing user admin
try:
    admin.site.unregister(User)
except admin.sites.NotRegistered:
    pass

admin.site.register(User, CustomUserAdmin)


# =====================================================
# USER SCOPE ADMIN
# =====================================================
@admin.register(UserScope)
class UserScopeAdmin(admin.ModelAdmin):
    list_display = ("user", "plant", "role")
    list_filter = ("plant", "role")
    search_fields = ("user__username", "user__email")
    autocomplete_fields = ("user", "plant", "role")


from core.audit.models import AuditLog, DomainEvent


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ("action", "actor", "object_type", "object_id", "created_at")
    list_filter = ("action", "object_type", "created_at")
    search_fields = ("action", "object_type", "object_id", "actor__username")
    readonly_fields = ("actor", "action", "object_type", "object_id", "metadata", "created_at")
    ordering = ("-created_at",)


@admin.register(DomainEvent)
class DomainEventAdmin(admin.ModelAdmin):
    list_display = ("event_type", "event_id", "object_type", "object_id", "created_at")
    list_filter = ("event_type", "object_type", "created_at")
    search_fields = ("event_type", "event_id", "object_type", "object_id")
    readonly_fields = ("event_id", "event_type", "object_type", "object_id", "payload", "created_at")
    ordering = ("-created_at",)