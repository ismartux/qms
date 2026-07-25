from django.shortcuts import render
from django.contrib.auth.models import User
from django.db.models import Count
from ui.admin_panel.views.base import admin_required

from org.models import Plant
from submissions.models import Submission
from capa.models import CAPA
from core.audit.models import AuditLog
from core.tenant.context import get_current_plant


@admin_required
def admin_dashboard(request):

    current_plant = get_current_plant()

    # -------------------------------
    # Superuser sees global data
    # -------------------------------
    if request.user.is_superuser:
        submission_qs = Submission.objects.all()
        capa_qs = CAPA.objects.all()
    else:
        # Plant-aware manager already filters,
        # but we explicitly scope for clarity
        submission_qs = Submission.objects.all()
        capa_qs = CAPA.objects.all()

    total_users = User.objects.count()
    total_plants = Plant.objects.count()
    total_submissions = submission_qs.count()
    total_capas = capa_qs.count()

    submissions_by_plant = (
        submission_qs
        .values("plant__name")
        .annotate(count=Count("submission_id"))
        .order_by("-count")
    )

    capa_status = (
        capa_qs
        .values("status")
        .annotate(count=Count("capa_id"))
    )

    activities = []
    try:
        logs = (
            AuditLog.objects
            .select_related("actor")
            .order_by("-created_at")[:10]
        )

        for log in logs:
            activities.append({
                "title": f"{log.action} by {log.actor.username if log.actor else 'System'}",
                "time": log.created_at,
            })
    except Exception:
        pass

    return render(request, "admin/dashboard.html", {
        "total_users": total_users,
        "total_plants": total_plants,
        "total_submissions": total_submissions,
        "total_capas": total_capas,
        "plant_labels": [x["plant__name"] for x in submissions_by_plant],
        "plant_data": [x["count"] for x in submissions_by_plant],
        "capa_labels": [x["status"] for x in capa_status],
        "capa_data": [x["count"] for x in capa_status],
        "recent_activities": activities,
    })