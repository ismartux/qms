from django.urls import path

from ui.admin_panel.views.dashboard import admin_dashboard
from ui.admin_panel.views.capas import (
    capa_management,
    capa_create,
    capa_edit
)
from ui.admin_panel.views.reports import (
    reports,
    generate_report
)

app_name = "admin_panel"

urlpatterns = [

    # ================= DASHBOARD =================
    path("", admin_dashboard, name="admin_dashboard"),

    # ================= CAPA =================
    path("capas/", capa_management, name="admin_capas"),
    path("capas/create/", capa_create, name="capa_create"),
    path("capas/<uuid:capa_id>/edit/", capa_edit, name="capa_edit"),

    # ================= REPORTS =================
    path("reports/", reports, name="reports"),
    path("reports/generate/", generate_report, name="generate_report"),
]
