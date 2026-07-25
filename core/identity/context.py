# core/identity/context.py

from core.identity.models import UserScope


def get_user_scope(user, *, work_context=None):
    """
    Resolve user's role via UserScope.

    Rules:
    - Role is plant-scoped (UserScope.user + plant)
    - WorkContext defines the active plant
    - Superuser → None (bypass role checks)
    """

    if not user or not user.is_authenticated:
        return None

    # 🔓 Superuser bypass (handled separately in views)
    if user.is_superuser:
        return None

    # -------------------------------------------------
    # Resolve work context
    # -------------------------------------------------
    if work_context is None:
        # Fallback: try to get active work context from user
        work_context = getattr(user, "active_work_context", None)

    if not work_context or not work_context.plant_id:
        return None

    # -------------------------------------------------
    # Resolve UserScope (user + plant → role)
    # -------------------------------------------------
    return (
        UserScope.objects
        .select_related("role", "department", "plant")
        .filter(
            user=user,
            plant=work_context.plant,
        )
        .first()
    )
    
    
    
def get_user_role(user, *, work_context=None):
    """
    Resolve user role.

    Rules:
    - Operator mode → role from UserScope(user + plant)
    - Standalone mode → role from ANY UserScope of user
    - Superuser → None (bypass)
    """

    if not user or not user.is_authenticated:
        return None

    # Superuser bypass
    if user.is_superuser:
        return None

    # -------------------------------------------------
    # OPERATOR MODE (plant-specific)
    # -------------------------------------------------
    if work_context and getattr(work_context, "plant_id", None):
        scope = (
            UserScope.objects
            .select_related("role")
            .filter(
                user=user,
                plant=work_context.plant,
            )
            .first()
        )
        return scope.role if scope else None

    # -------------------------------------------------
    # STANDALONE MODE (NO WORK CONTEXT)
    # Use ANY UserScope for this user
    # -------------------------------------------------
    scope = (
        UserScope.objects
        .select_related("role")
        .filter(user=user)
        .order_by("id")   # deterministic
        .first()
    )
    return scope.role if scope else None