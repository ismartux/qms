from core.identity.permissions import has_permission
from core.tenant.context import get_current_plant


def permission_context(request):
    """
    Sidebar + template permission context.
    Fully dynamic, DB-driven, plant-aware.
    """

    if not request.user.is_authenticated:
        return {}

    user = request.user
    current_plant = get_current_plant()

    # -------------------------------------------------
    # 🔒 Check if user has any scope in current plant
    # -------------------------------------------------
    scopes_qs = user.scopes.all() if hasattr(user, "scopes") else None

    if scopes_qs and current_plant:
        scopes_qs = scopes_qs.filter(plant=current_plant)

    has_scopes = scopes_qs.exists() if scopes_qs else False

    # -------------------------------------------------
    # Resolve current app / url (menu highlighting)
    # -------------------------------------------------
    resolver = request.resolver_match
    current_app = resolver.app_name if resolver else ""
    current_url = resolver.url_name if resolver else ""

    # -------------------------------------------------
    # Permission Checks (evaluated once)
    # -------------------------------------------------
    permissions = {
        # QUALITY
        "can_fill_forms": has_permission(user, "can_fill_forms"),
        "can_submit": has_permission(user, "can_submit"),
        "can_manage_capa": has_permission(user, "can_manage_capa"),
        "can_approve_ipqc": has_permission(user, "can_approve_ipqc"),
        "can_view_analytics": has_permission(user, "can_view_analytics"),
        "can_manage_users": has_permission(user, "can_manage_users"),
        "can_view_submissions": has_permission(user, "can_view_submissions"),

        # 🔥 EHS
        "can_fill_ehs_forms": has_permission(user, "can_fill_ehs_forms"),
        "can_submit_ehs": has_permission(user, "can_submit_ehs"),
        "can_view_ehs_reports": has_permission(user, "can_view_ehs_reports"),
        "can_manage_ehs_templates": has_permission(user, "can_manage_ehs_templates"),
        "can_approve_ehs": has_permission(user, "can_approve_ehs"),
    }

    return {
        # -------------------------------------------------
        # 🔐 Permissions (PRIMARY API)
        # -------------------------------------------------
        **permissions,

        # -------------------------------------------------
        # Platform Flags (SAFE)
        # -------------------------------------------------
        "is_superuser": user.is_superuser,
        "is_admin": user.is_superuser or permissions["can_manage_users"],
        "has_scopes": has_scopes,

        # -------------------------------------------------
        # UI Helpers
        # -------------------------------------------------
        "current_app": current_app,
        "current_url": current_url,
    }