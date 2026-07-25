def is_admin(user):
    if not user.is_authenticated:
        return False

    if user.is_superuser:
        return True

    # platform admins via group
    return user.groups.filter(
        name__in=["Platform Admin", "Admin"]
    ).exists()
