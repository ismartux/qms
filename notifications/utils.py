from django.conf import settings
from .models import LarkConfig
from django.core.exceptions import ObjectDoesNotExist

def get_lark_webhook(alert_type: str) -> str | None:
    """Return the webhook URL for a given alert type.

    Args:
        alert_type: Name of webhook group (e.g. "IPQC", "EHS", "error", "warning", "FormMissed", "Approval").

    Checks LarkConfig DB model first, then falls back to settings.LARK_WEBHOOKS, and finally settings.LARK_DEFAULT_WEBHOOK.
    """
    if not alert_type:
        return getattr(settings, "LARK_DEFAULT_WEBHOOK", None)

    try:
        config = LarkConfig.objects.filter(name__iexact=alert_type).first()
        if config and config.webhook_url and config.webhook_url.strip():
            return config.webhook_url.strip()
    except Exception:
        pass

    lark_webhooks = getattr(settings, "LARK_WEBHOOKS", {})
    if isinstance(lark_webhooks, dict):
        if alert_type in lark_webhooks:
            return lark_webhooks[alert_type]
        for key, url in lark_webhooks.items():
            if str(key).upper() == str(alert_type).upper():
                return url

    return getattr(settings, "LARK_DEFAULT_WEBHOOK", None)
