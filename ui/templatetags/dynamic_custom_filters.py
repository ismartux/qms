from django import template

register = template.Library()


@register.filter
def get_item(mapping, key):
    """
    Safe dict lookup in templates.

    Usage:
        {{ my_dict|get_item:key }}
    """
    try:
        return mapping.get(str(key))
    except Exception:
        return None