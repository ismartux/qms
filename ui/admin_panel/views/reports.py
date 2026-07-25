from django.shortcuts import render
from django.http import JsonResponse
from django.template.loader import render_to_string
from django.utils import timezone
from datetime import timedelta
from django.db.models import Avg

from ui.admin_panel.views.base import admin_required
from submissions.models import Submission
from capa.models import CAPA


@admin_required
def reports(request):
    return render(request, "admin/reports/index.html")


@admin_required
def generate_report(request):
    report_type = request.GET.get("reportType")
    date_range = request.GET.get("dateRange", "month")

    now = timezone.now()

    if date_range == "month":
        start_datetime = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        end_datetime = now
    else:
        start_datetime = now.replace(hour=0, minute=0, second=0, microsecond=0)
        end_datetime = now

    # ==============================
    # SUBMISSIONS REPORT
    # ==============================
    if report_type == "submissions":

        submissions = (
            Submission.objects
            .filter(created_at__range=(start_datetime, end_datetime))
            .select_related(
                "plant",
                "line",
                "product",
                "template_version",
            )
        )

        total_submissions = submissions.count()

        avg_severity = (
            submissions.aggregate(avg=Avg("severity_score"))["avg"] or 0
        )

        html = render_to_string(
            "admin/reports/submissions_report.html",
            {
                "submissions": submissions,
                "total_submissions": total_submissions,
                "avg_severity": avg_severity,
            },
        )

    # ==============================
    # CAPA REPORT
    # ==============================
    elif report_type == "capas":

        capas = (
            CAPA.objects
            .filter(created_at__range=(start_datetime, end_datetime))
        )

        total_capas = capas.count()

        html = render_to_string(
            "admin/reports/capas_report.html",
            {
                "capas": capas,
                "total_capas": total_capas,
            },
        )

    else:
        return JsonResponse({"success": False})

    return JsonResponse({"success": True, "html": html})