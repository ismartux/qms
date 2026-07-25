from django import template
from core.identity.access import has_access

register = template.Library()


@register.simple_tag(takes_context=True)
def can_access(context, **rules):
    """
    Template permission check.

    Usage:
        {% can_access roles="ADMIN" as can_view %}
        {% if can_view %}
            ...
        {% endif %}
    """

    request = context.get("request")
    if not request:
        return False

    user = getattr(request, "user", None)
    if not user or not user.is_authenticated:
        return False

    # Superuser shortcut (avoid unnecessary permission evaluation)
    if user.is_superuser:
        return True

    # Cache per-request permission checks
    cache_key = f"_perm_cache_{hash(frozenset(rules.items()))}"

    if not hasattr(request, cache_key):
        setattr(
            request,
            cache_key,
            has_access(user, **rules),
        )

    return getattr(request, cache_key)