import logging
import threading
from django.core.cache import cache
from .services import run_scheduler, detect_and_alert_missed_forms

logger = logging.getLogger(__name__)


def _run_bg_task(func, name):
    try:
        func()
    except Exception as e:
        logger.error(f"Error in background task {name}: {e}")


class SchedulerMiddleware:

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.user.is_authenticated:
            # Global application-wide cache lock for scheduler checks (5 min throttle)
            if not cache.get("qms_scheduler_ran"):
                cache.set("qms_scheduler_ran", True, 300)  # 5 minutes
                t = threading.Thread(target=_run_bg_task, args=(run_scheduler, "run_scheduler"), daemon=True)
                t.start()

            # Global application-wide cache lock for missed form alerts (15 min throttle)
            if not cache.get("qms_missed_forms_alert_ran"):
                cache.set("qms_missed_forms_alert_ran", True, 900)  # 15 minutes
                t = threading.Thread(target=_run_bg_task, args=(detect_and_alert_missed_forms, "detect_and_alert_missed_forms"), daemon=True)
                t.start()

        return self.get_response(request)

