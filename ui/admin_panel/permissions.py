def is_admin(user):
    if not user.is_authenticated:
        return False

    if user.is_superuser:
        return True

    # platform admins via group
    if user.groups.filter(
        name__in=["Platform Admin", "Admin"]
    ).exists():
        return True

    # Check for the can_access_admin_panel permission
    from core.identity.permissions import has_permission
    if has_permission(user, 'can_access_admin_panel'):
        return True

    return False
