from django.contrib.auth.models import AnonymousUser


def admin_access(request):
    """
    Determines whether user has admin access.
    Preserves existing logic:
    - Superuser = admin
    - Group 'Admin' or 'Platform Admin' = admin
    """

    user = getattr(request, "user", None)

    if not user or isinstance(user, AnonymousUser):
        return {"has_admin_access": False}

    if not user.is_authenticated or not user.is_active:
        return {"has_admin_access": False}

    # Superuser always admin
    if user.is_superuser:
        return {"has_admin_access": True}

    # Group-based admin access
    if user.groups.filter(
        name__in=["Admin", "Platform Admin"]
    ).exists():
        return {"has_admin_access": True}

    return {"has_admin_access": False}


def ui_context(request):
    """
    Determines whether current route belongs to admin panel.
    Preserves existing behavior.
    """

    resolver = getattr(request, "resolver_match", None)

    admin_apps = {
        "admin_panel",
        "transs_admin_flow",
        "ehs_builder",
        "accounts",
        "identity",
    }

    is_admin_panel = False

    if resolver and resolver.app_name:
        is_admin_panel = resolver.app_name in admin_apps

    return {
        "is_admin_panel": is_admin_panel,
    }