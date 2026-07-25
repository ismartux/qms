# analytics/views.py

import json
from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from django.core.serializers.json import DjangoJSONEncoder

from core.context import get_current_plant
from core.identity.permissions import has_permission

from analytics.dashboards.ipqc import IPQCDashboard
from analytics.dashboards.management import ManagementDashboard
from analytics.dashboards.pqe import PQEDashboard
from analytics.dashboards.tlam import TLAMDashboard


@login_required
def role_dashboard(request):
    """
    Central role-based dashboard router.
    Clean separation:
    - Superuser → Management (HQ)
    - PQE → Quality analytics
    - TL/AM → Risk overview
    - IPQC → Operational dashboard
    """

    user = request.user
    plant = None

    # --------------------------------------------------
    # Resolve plant (for non-superusers)
    # --------------------------------------------------
    if not user.is_superuser:
        try:
            plant = get_current_plant(request)
        except Exception:
            plant = None

    # ==================================================
    # ================= MANAGEMENT (HQ) =================
    # ==================================================
    if user.is_superuser:

        data = ManagementDashboard.build()

        context = {
            "kpis": data.get("kpis", {}),
            "capa_summary": data.get("capa_summary", {}),
            "plant_comparison": json.dumps(
                list(data.get("plant_comparison", [])),
                cls=DjangoJSONEncoder
            ),
            "trend": json.dumps(
                list(data.get("trend", [])),
                cls=DjangoJSONEncoder
            ),
            "template_comparison": json.dumps(
                list(data.get("template_comparison", [])),
                cls=DjangoJSONEncoder
            ),
        }

        return render(
            request,
            "analytics/management_dashboard.html",
            context
        )

    # ==================================================
    # ====================== PQE ========================
    # ==================================================
    if has_permission(user, "can_manage_capa"):

        data = PQEDashboard.build(plant)

        context = {
            "trend": json.dumps(
                list(data.get("trend", [])),
                cls=DjangoJSONEncoder
            ),
            "pareto": json.dumps(
                list(data.get("pareto", [])),
                cls=DjangoJSONEncoder
            ),
            "template_comparison": json.dumps(
                list(data.get("template_comparison", [])),
                cls=DjangoJSONEncoder
            ),
        }

        return render(
            request,
            "analytics/pqe_dashboard.html",
            context
        )

    # ==================================================
    # ====================== TL / AM ====================
    # ==================================================
    if has_permission(user, "workcontext.view_all"):

        data = TLAMDashboard.build(plant)

        context = {
            "kpis": data.get("kpis", {}),
            "capa": data.get("capa", {}),
            "risk_index": data.get("risk_index", 0),
        }

        return render(
            request,
            "analytics/tlam_dashboard.html",
            context
        )

    # ==================================================
    # ====================== IPQC =======================
    # ==================================================

    data = IPQCDashboard.build(plant)

    context = {
        "plant": plant,
        "kpis": data.get("kpis", {}),
        "trend": json.dumps(
            list(data.get("trend", [])),
            cls=DjangoJSONEncoder
        ),
        "capa_summary": data.get("capa_summary", {}),
        "severity_distribution": json.dumps(
            list(data.get("severity_distribution", [])),
            cls=DjangoJSONEncoder
        ),
    }

    return render(
        request,
        "analytics/ipqc_dashboard.html",
        context
    )
