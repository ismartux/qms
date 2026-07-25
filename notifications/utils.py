from .models import LarkConfig
from django.core.exceptions import ObjectDoesNotExist

def get_lark_webhook(alert_type: str) -> str | None:
    """Return the webhook URL for a given alert type.

    Args:
        alert_type: One of "error", "warning", or any custom name used for forms.

    The function looks up a ``LarkConfig`` entry whose ``name`` matches the
    ``alert_type`` (case‑insensitive).  If no entry exists ``None`` is returned.
    """
    try:
        config = LarkConfig.objects.get(name__iexact=alert_type)
        return config.webhook_url
    except (LarkConfig.DoesNotExist, ObjectDoesNotExist, Exception):
        return None
