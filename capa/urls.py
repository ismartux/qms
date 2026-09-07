from django.urls import path
from . import views

app_name = "capa"

urlpatterns = [

    # ================= LISTS & DASHBOARD =================
    path("", views.capa_list_view, name="capa_list_view"),
    path("dashboard/", views.capa_dashboard_view, name="capa_dashboard"),
    path("dashboard/details-api/", views.capa_dashboard_details_api, name="capa_dashboard_details_api"),
    path("<uuid:capa_id>/popup/", views.capa_popup_view, name="capa_popup"),
    path("my/", views.my_assigned_capas, name="my_assigned_capas"),
    path("approval/", views.approval_pending_capas, name="approval_pending_capas"),

    # ================= DETAIL / WORK =================
    path("<uuid:capa_id>/", views.capa_detail_view, name="capa_detail"),
    path("<uuid:capa_id>/work/", views.capa_work_view, name="capa_work"),

    # ================= PQE ACTIONS =================
    path("<uuid:capa_id>/approve/", views.capa_approve, name="capa_approve"),
    path("<uuid:capa_id>/reject/", views.capa_reject, name="capa_reject"),
]
