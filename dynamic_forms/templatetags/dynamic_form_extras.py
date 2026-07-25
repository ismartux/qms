from django import template

register = template.Library()

@register.filter
def get_item(obj, key):
    """
    Safe dictionary access for templates.
    """
    if not isinstance(obj, dict):
        return ""

    # UUID keys often become strings after JSON serialization
    return obj.get(str(key)) or obj.get(key) or ""