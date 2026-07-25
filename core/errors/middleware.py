import traceback
from datetime import datetime
from django.conf import settings
from django.core.exceptions import PermissionDenied
from django.http import Http404
from django.utils import timezone

from integrations.bitable.lark_service import LarkService


class GlobalExceptionMiddleware:

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        return self.get_response(request)

    # 🔥 Django exception hook
    def process_exception(self, request, exception):

        # ---------------------------------------
        # 🚫 Skip expected / harmless errors
        # ---------------------------------------
        if isinstance(exception, (PermissionDenied, Http404)):
            return None

        # ---------------------------------------
        # 🚫 Skip in DEBUG mode
        # ---------------------------------------
        if settings.DEBUG:
            return None

        try:
            # ---------------------------------------
            # 👤 User Info
            # ---------------------------------------
            if hasattr(request, "user") and request.user.is_authenticated:
                user = request.user
                username = user.username
                user_id = user.id

                # Safe role resolution (avoid unexpected crash)
                scope = getattr(user, "scopes", None)
                if scope:
                    scope_obj = scope.select_related("role").first()
                    role_code = (
                        scope_obj.role.code
                        if scope_obj and scope_obj.role
                        else "NO_ROLE"
                    )
                else:
                    role_code = "NO_SCOPE"
            else:
                username = "Anonymous"
                user_id = "N/A"
                role_code = "N/A"

            # ---------------------------------------
            # 🌐 Request Info
            # ---------------------------------------
            url = request.build_absolute_uri()
            method = request.method
            ip = request.META.get("REMOTE_ADDR", "Unknown")

            # ---------------------------------------
            # 🕒 Timestamp (timezone-safe)
            # ---------------------------------------
            timestamp = timezone.now().strftime("%Y-%m-%d %H:%M:%S")

            # ---------------------------------------
            # 📛 Error Info
            # ---------------------------------------
            error_message = str(exception)
            error_trace = traceback.format_exc()

            # Prevent extremely large payload
            if len(error_trace) > 3500:
                error_trace = error_trace[:3500] + "\n... (truncated)"

            # ---------------------------------------
            # 📤 Send To Lark
            # ---------------------------------------
            webhook = None
            try:
                from notifications.models import LarkConfig
                webhook = LarkConfig.objects.filter(name="Error").first().webhook_url if LarkConfig.objects.filter(name="Error").exists() else None
            except Exception:
                webhook = None

            if webhook:
                LarkService.send_message(
                    webhook=webhook,
                    title="🚨 TRANSS FLOW PRODUCTION ERROR",
                    lines=[
                        f"🕒 Time: {timestamp}",
                        f"👤 User: {username}",
                        f"🆔 User ID: {user_id}",
                        f"🏷 Role: {role_code}",
                        f"🌐 URL: {url}",
                        f"📡 Method: {method}",
                        f"🖥 IP: {ip}",
                        "",
                        f"❗ Error: {error_message}",
                        "",
                        "🧾 Traceback:",
                        error_trace,
                    ]
                )

        except Exception:
            # Never allow reporting to crash request handling
            pass

        # Let Django continue normal 500 handling
        return None