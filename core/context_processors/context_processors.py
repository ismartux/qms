from core.identity.permissions import has_permission
from core.tenant.context import get_current_plant


def role_flags(request):
    """
    Exposes permission-based flags to templates.
    Fully dynamic, DB-driven, plant-aware.
    """

    if not request.user.is_authenticated:
        return {}

    user = request.user
    current_plant = get_current_plant()

    # -------------------------------------------------
    # 🔒 Scope permissions to current plant (if exists)
    # -------------------------------------------------
    scopes_qs = user.scopes.all()

    if current_plant:
        scopes_qs = scopes_qs.filter(plant=current_plant)

    has_scopes = scopes_qs.exists()

    return {

        # =========================
        # PLATFORM FLAGS
        # =========================
        "is_superuser": user.is_superuser,
        "has_scopes": has_scopes,

        # =========================
        # QUALITY PERMISSIONS
        # =========================
        "can_fill_forms": has_permission(user, "can_fill_forms"),
        "can_submit": has_permission(user, "can_submit"),
        "can_manage_capa": has_permission(user, "can_manage_capa"),
        "can_approve_ipqc": has_permission(user, "can_approve_ipqc"),
        "can_view_analytics": has_permission(user, "can_view_analytics"),
        "can_view_submissions": has_permission(user, "can_view_submissions"),
        "can_manage_users": has_permission(user, "can_manage_users"),

        # =========================
        # 🔥 EHS PERMISSIONS
        # =========================
        "can_fill_ehs_forms": has_permission(user, "can_fill_ehs_forms"),
        "can_submit_ehs": has_permission(user, "can_submit_ehs"),
        "can_view_ehs_reports": has_permission(user, "can_view_ehs_reports"),
        "can_manage_ehs_templates": has_permission(user, "can_manage_ehs_templates"),
        "can_approve_ehs": has_permission(user, "can_approve_ehs"),
    }