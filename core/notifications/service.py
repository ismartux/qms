from django.contrib.auth import get_user_model
from core.audit.models import DomainEvent
from core.tenant.context import get_current_plant  # if using middleware


User = get_user_model()


def resolve_recipients(event: DomainEvent):
    """
    Resolve recipients for system events.

    Preserves existing severity logic.
    Adds plant-level isolation if plant_id is available.
    """

    severity = event.payload.get("severity", 0)
    plant_id = event.payload.get("plant_id")

    queryset = User.objects.all()

    # --------------------------------------------------
    # Apply plant isolation if plant_id exists
    # --------------------------------------------------
    if plant_id:
        queryset = queryset.filter(
            scopes__plant_id=plant_id  # assuming UserScope model
        )

    # --------------------------------------------------
    # Event-based resolution
    # --------------------------------------------------
    if event.event_type == "SUBMISSION_SUBMITTED":
        if severity >= 8:
            return queryset.filter(groups__name="Admin").distinct()
        if severity >= 3:
            return queryset.filter(groups__name="PQE").distinct()

    if event.event_type == "CAPA_CREATED":
        return queryset.filter(
            groups__name__in=["PQE", "Admin"]
        ).distinct()

    return User.objects.none()