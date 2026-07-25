from ehs_engine.models import EHSNotification


def notification_context(request):
    if not request.user.is_authenticated:
        return {}

    unread = EHSNotification.objects.filter(
        recipient=request.user,
        is_read=False
    ).count()

    latest_notifications = EHSNotification.objects.filter(
        recipient=request.user
    ).order_by("-created_at")[:5]

    return {
        "ehs_unread_notifications": unread,
        "ehs_latest_notifications": latest_notifications,
    }