# =====================================================
# Role → Permission map (SOURCE OF TRUTH)
# =====================================================

# ROLE_PERMISSIONS = {

#     # ======================
#     # QUALITY ROLES
#     # ======================

#     Roles.OPERATOR: {
#         "can_fill_forms": True,
#         "can_submit": True,
#     },

#     Roles.IPQC: {
#         "can_fill_forms": True,
#         "can_submit": True,
#         "can_view_analytics": True,
#     },

#     Roles.IPQC_PACK: {
#         "can_fill_forms": True,
#         "can_submit": True,
#         "can_view_analytics": True,
#     },

#     Roles.PQE: {
#         "can_manage_capa": True,
#         "can_approve_ipqc": True,
#     },

#     Roles.ADMIN: {
#         "can_view_analytics": True,
#         "can_manage_users": True,
#         "can_override": True,
#         "can_approve_ipqc": True,
#     },

#     # ======================
#     # 🔥 EHS ROLES
#     # ======================

#     Roles.EHS_AUDITOR: {
#         "can_fill_ehs_forms": True,
#         "can_submit_ehs": True,
#         "can_view_ehs_reports": True,
#     },

#     Roles.EHS_ADMIN: {
#         "can_fill_ehs_forms": True,
#         "can_submit_ehs": True,
#         "can_view_ehs_reports": True,
#         "can_manage_ehs_templates": True,
#         "can_approve_ehs": True,
#         "can_manage_ehs_settings": True,
#     },
# }


# =====================================================
# Permission resolver (ROLE + USERSCOPE BASED)
# =====================================================

def has_permission(user, permission_code: str) -> bool:
    if not user or not user.is_authenticated:
        return False

    # Superuser bypass
    if user.is_superuser:
        return True

    scopes = getattr(user, "scopes", None)
    if not scopes:
        return False

    # Request-level cache
    cached = getattr(user, "_cached_permissions", None)

    if cached is None:
        cached = set(
            scopes
            .select_related("role")
            .prefetch_related(
                "role__role_permissions__permission"
            )
            .values_list(
                "role__role_permissions__permission__code",
                flat=True
            )
        )
        user._cached_permissions = cached

    return permission_code in cached


def is_platform_admin(user):
    """
    Platform-level admin (not plant-scoped).
    """
    return bool(
        user and user.is_authenticated and (
            user.is_superuser or user.is_staff
        )
    )