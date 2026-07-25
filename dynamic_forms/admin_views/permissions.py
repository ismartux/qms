from django.core.exceptions import PermissionDenied
from core.identity.permissions import has_permission, is_platform_admin


DYNAMIC_FORM_BUILDER_PERMISSION = "DYNAMIC_FORM_BUILDER"


def require_dynamic_form_builder(user):
    """
    Enforces Dynamic Form Builder access using platform RBAC.
    """

    if not user or not user.is_authenticated:
        raise PermissionDenied

    # Platform admin bypass
    if is_platform_admin(user):
        return

    if not has_permission(user, DYNAMIC_FORM_BUILDER_PERMISSION):
        raise PermissionDenied