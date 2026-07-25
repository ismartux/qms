import logging
from django.conf import settings
from django.db import transaction

logger = logging.getLogger(__name__)


# ==========================================================
# WEB (IN-APP) NOTIFICATION
# ==========================================================
def send_web_notification(user, title, message):
    """
    Placeholder for in-app inbox notification.
    Safe: will never break request cycle.
    """

    try:
        # Keep existing behavior (non-breaking)
        print(f"[WEB] To {user.username}: {title} - {message}")

        # Future: hook for database inbox model here

    except Exception as e:
        logger.exception(
            "Failed to send web notification",
            extra={"user_id": getattr(user, "id", None)}
        )


# ==========================================================
# EMAIL NOTIFICATION
# ==========================================================
def send_email_notification(user, subject, message):
    """
    Safe email sending.
    - Does not crash workflow
    - Logs failures
    - Supports async pattern
    """

    if not user or not getattr(user, "email", None):
        return

    def _send():
        try:
            user.email_user(subject, message)
        except Exception:
            logger.exception(
                "Email notification failed",
                extra={
                    "user_id": getattr(user, "id", None),
                    "email": user.email,
                }
            )

    # If inside transaction → send AFTER commit
    try:
        transaction.on_commit(_send)
    except Exception:
        # If not in transaction context
        _send()