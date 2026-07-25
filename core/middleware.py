import pytz
from django.utils import timezone
from core.context import get_active_work_context
from core.context import get_current_plant

# 🔥 NEW: import tenant context helpers (safe if exists)
try:
    from core.tenant.context import set_current_plant, clear_current_plant
except Exception:
    set_current_plant = None
    clear_current_plant = None


class PlantTimezoneMiddleware:
    """
    Activate plant timezone for the current request.
    Safe & rollback-protected.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        tz = None

        try:
            work_context = get_active_work_context(request)
        except Exception:
            work_context = None

        if (
            work_context
            and getattr(work_context, "plant_id", None)
            and getattr(work_context.plant, "timezone", None)
        ):
            try:
                tz = pytz.timezone(work_context.plant.timezone)
            except Exception:
                tz = None

        if tz:
            timezone.activate(tz)
        else:
            timezone.deactivate()

        try:
            response = self.get_response(request)
        finally:
            # Always reset timezone after request
            timezone.deactivate()

        return response


class PlantContextMiddleware:
    """
    Attach plant to request and sync tenant context.
    Does NOT break existing logic.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):

        request.plant = None

        if request.user.is_authenticated:
            try:
                plant = get_current_plant(request)
                request.plant = plant

                # 🔥 Sync with tenant isolation context (if available)
                if set_current_plant:
                    set_current_plant(plant)

            except Exception:
                request.plant = None

        try:
            response = self.get_response(request)
        finally:
            # 🔥 Clear tenant context safely
            if clear_current_plant:
                clear_current_plant()

        return response


class SessionSanitizerMiddleware:
    """
    HARD GUARD middleware.

    Removes poisoned session values BEFORE any other middleware/view runs.
    Prevents:
    - Field 'id' expected a number but got ''
    - UUID/int FK crashes
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):

        session = request.session
        bad = False

        # 🔥 CLEAN BAD WORK CONTEXT ID
        ctx_id = session.get("active_work_context_id")
        if ctx_id in ("", False, None):
            bad = True

        exec_ctx = session.get("execution_context")

        if isinstance(exec_ctx, dict):
            for key in ("plant_id", "line_id", "product_id"):
                if exec_ctx.get(key) in ("", None):
                    bad = True

        if bad:
            session.pop("active_work_context_id", None)
            session.pop("execution_context", None)
            session.modified = True

        return self.get_response(request)