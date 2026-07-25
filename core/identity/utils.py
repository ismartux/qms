from core.identity.models import UserScope


def get_user_active_role(user, plant=None):
    """
    Returns the active Role for the user.

    Priority:
    1. If plant is provided → scope for that plant
    2. Else → first available scope (fallback)

    Raises ValueError if no scope exists.
    """

    qs = UserScope.objects.filter(user=user)

    if plant:
        scope = qs.filter(plant=plant).select_related("role").first()
        if scope:
            return scope.role

    scope = qs.select_related("role").first()
    if scope:
        return scope.role

    raise ValueError("User has no active role scope")