from core.notifications.service import resolve_recipients
from core.notifications.channels import send_web_notification
from core.tenant.context import set_current_plant, clear_current_plant


def dispatch_event(event):
    """
    Dispatch notification event safely with plant isolation.

    Works for:
    - HTTP requests
    - Celery tasks
    - Management commands
    """

    plant_id = None

    # Try extracting plant_id from event metadata (recommended)
    if hasattr(event, "metadata") and event.metadata:
        plant_id = event.metadata.get("plant_id")

    try:
        if plant_id:
            # Lazy import to avoid circular dependency
            from org.models import Plant
            plant = Plant.objects.filter(id=plant_id).first()
            if plant:
                set_current_plant(plant)

        users = resolve_recipients(event)

        for user in users:
            send_web_notification(
                user,
                title=event.event_type,
                message=f"{event.object_type} {event.object_id}",
            )

    finally:
        # Always clear context
        clear_current_plant()