from django.shortcuts import render, redirect
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.views.decorators.http import require_http_methods
from django.conf import settings
from core.tenant.context import get_current_plant
from integrations.bitable.lark_service import LarkService


# =========================================
# ROLE → WEBHOOK GROUP MAP (MOVE OUTSIDE VIEW)
# =========================================
ROLE_WEBHOOK_MAP = {
    "EHS_AUDITOR": "EHS",
    "EHS_ADMIN": "EHS",
    "IPQC": "IPQC",
    "IPQC_PACK": "IPQC",
    "PQE": "IPQC",
    "ADMIN": "IPQC",
}


@login_required
@require_http_methods(["GET", "POST"])
def bitable_send_lark_broadcast(request):

    # =========================================
    # MULTI-PLANT ISOLATION
    # =========================================
    current_plant = get_current_plant()

    if not current_plant:
        raise PermissionDenied("No active plant context.")

    # =========================================
    # RESOLVE USER ROLE FOR CURRENT PLANT
    # =========================================
    scope = (
        request.user.scopes
        .select_related("role", "plant")
        .filter(plant=current_plant)
        .first()
    )

    if not scope or not scope.role:
        raise PermissionDenied("No role assigned for this plant.")

    role_code = scope.role.code.upper()

    # =========================================
    # MAP ROLE → WEBHOOK GROUP
    # =========================================
    webhook_key = ROLE_WEBHOOK_MAP.get(role_code)

    if not webhook_key:
        raise PermissionDenied(
            f"No webhook mapping for role: {role_code}"
        )

    webhook = settings.LARK_WEBHOOKS.get(webhook_key)

    if not webhook:
        raise PermissionDenied(
            f"No webhook configured for key: {webhook_key}"
        )

    # =========================================
    # HANDLE POST
    # =========================================
    if request.method == "POST":

        message = request.POST.get("message", "").strip()

        if not message:
            messages.error(request, "Message cannot be empty.")
            return redirect(request.path)

        # Optional: simple length guard
        if len(message) > 2000:
            messages.error(request, "Message too long.")
            return redirect(request.path)

        success = LarkService.send_message(
            webhook=webhook,
            title=f"📢 {webhook_key} Broadcast",
            lines=[
                f"Plant: {current_plant.name}",
                f"Sent By: {request.user.username}",
                message,
            ]
        )

        if success:
            messages.success(request, "Message sent successfully.")
        else:
            messages.error(request, "Failed to send message.")

        return redirect(request.META.get("HTTP_REFERER", "/"))

    # =========================================
    # SHOW FORM
    # =========================================
    return render(
        request,
        "ehs_engine/lark_broadcast.html",
        {
            "role": role_code,
            "group": webhook_key,
            "plant": current_plant,
        }
    )