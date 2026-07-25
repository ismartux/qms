from typing import Optional, Dict
from uuid import UUID

from django.http import HttpRequest
from django.core.exceptions import PermissionDenied
from django.db.models import Q

from core.identity.models import UserScope
from org.models import Plant
from submissions.models import WorkContext


CONTEXT_SESSION_KEY = "execution_context"
ACTIVE_WORK_CONTEXT_KEY = "active_work_context_id"


# -------------------------------------------------------------------
# PLANT RESOLUTION
# -------------------------------------------------------------------

def resolve_user_plant(user) -> Plant:
    """
    Resolve plant for the logged-in user.

    Rules:
    - Superuser: bypass (returns first plant)
    - Normal user: MUST be assigned to exactly ONE plant
    """

    if user.is_superuser:
        plant = Plant.objects.filter(is_active=True).first()
        if not plant:
            raise RuntimeError("No plants configured in the system")
        return plant

    scopes = (
        UserScope.objects
        .select_related("plant")
        .filter(user=user, plant__is_active=True)
    )

    count = scopes.count()

    if count == 0:
        raise PermissionDenied("User is not assigned to any active plant")

    if count > 1:
        raise PermissionDenied(
            "User assigned to multiple plants. "
            "This system requires exactly one plant per user."
        )

    return scopes.first().plant


# -------------------------------------------------------------------
# EXECUTION CONTEXT (SESSION-BASED)
# -------------------------------------------------------------------

def ensure_execution_context(request: HttpRequest) -> Dict:

    if not request.user.is_authenticated:
        raise PermissionDenied("Unauthenticated request")

    session = request.session

    plant = resolve_user_plant(request.user)

    context = session.get(CONTEXT_SESSION_KEY)

    if not isinstance(context, dict):
        context = {
            "plant_id": plant.id,
            "line_id": None,
            "station_id": None,
            "product_id": None,
        }
        session[CONTEXT_SESSION_KEY] = context
        session.modified = True

    # 🔒 Hard enforce plant consistency
    if context.get("plant_id") != plant.id:
        context.update({
            "plant_id": plant.id,
            "line_id": None,
            "station_id": None,
            "product_id": None,
        })
        session[CONTEXT_SESSION_KEY] = context
        session.modified = True

    return context


def update_execution_context(
    request: HttpRequest,
    *,
    line_id: int,
    product_id: int,
    station_id: Optional[int] = None,
) -> Dict:

    context = ensure_execution_context(request)

    context.update({
        "line_id": int(line_id),
        "product_id": int(product_id),
        "station_id": int(station_id) if station_id else None,
    })

    request.session[CONTEXT_SESSION_KEY] = context
    request.session.modified = True

    return context


def get_execution_context(request: HttpRequest) -> Optional[Dict]:
    context = request.session.get(CONTEXT_SESSION_KEY)
    return context if isinstance(context, dict) else None


def clear_execution_context(request: HttpRequest):
    request.session.pop(CONTEXT_SESSION_KEY, None)
    request.session.pop(ACTIVE_WORK_CONTEXT_KEY, None)
    request.session.modified = True


def has_valid_execution_context(context: Optional[Dict]) -> bool:

    if not isinstance(context, dict):
        return False

    return all([
        context.get("plant_id"),
        context.get("line_id"),
        context.get("product_id"),
    ])


# -------------------------------------------------------------------
# WORK CONTEXT (DB-BASED)
# -------------------------------------------------------------------

def get_active_work_context(request: HttpRequest) -> Optional[WorkContext]:
    """
    Return a REAL WorkContext from DB or None.
    Strict plant validation enforced.
    """

    context_id = request.session.get(ACTIVE_WORK_CONTEXT_KEY)

    if not context_id:
        return None

    try:
        UUID(str(context_id))
    except Exception:
        request.session.pop(ACTIVE_WORK_CONTEXT_KEY, None)
        request.session.modified = True
        return None

    current_plant = get_current_plant(request)

    try:
        return WorkContext.objects.get(
            id=context_id,
            is_active=True,
            plant=current_plant,   # 🔒 CRITICAL PLANT ENFORCEMENT
        )
    except WorkContext.DoesNotExist:
        request.session.pop(ACTIVE_WORK_CONTEXT_KEY, None)
        request.session.modified = True
        return None


# -------------------------------------------------------------------
# CURRENT PLANT (SAFE RESOLUTION)
# -------------------------------------------------------------------

def get_current_plant(request: HttpRequest) -> Plant:
    """
    Resolve current plant safely.

    Priority:
    1. Superuser bypass
    2. Execution context
    3. UserScope
    """

    if request.user.is_superuser:
        plant = Plant.objects.filter(is_active=True).first()
        if plant:
            return plant
        raise RuntimeError("No active plants exist in the system")

    # 1️⃣ Execution context
    context = request.session.get(CONTEXT_SESSION_KEY)

    if isinstance(context, dict):
        plant_id = context.get("plant_id")
        if plant_id:
            try:
                return Plant.objects.get(id=plant_id, is_active=True)
            except Plant.DoesNotExist:
                pass

    # 2️⃣ Fallback to user scope
    return resolve_user_plant(request.user)