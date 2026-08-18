from django.urls import path
from ui import views

app_name = "ui"

urlpatterns = [

    # =====================================================
    # HOME
    # =====================================================
    path("", views.main_home, name="main_home"),
    path("ipqc/home/", views.operator_home, name="operator_home"),


    # =====================================================
    # FORMS (IPQC)
    # =====================================================
    path("forms/", views.forms_list_view, name="forms_list"),
    path("forms/<str:code>/", views.form_runtime_view, name="form_runtime"),
    path(
        "forms/runtime/<str:engine>/<str:template_id>/",
        views.unified_form_runtime_view,
        name="unified_form_runtime",
    ),
    # Standalone Dynamic
    path("dynamic/forms/", views.dynamic_forms_list_view, name="dynamic_forms_list"),
    path("dynamic/forms/<uuid:template_id>/", views.dynamic_form_runtime_view, name="dynamic_form_runtime"),

    # =====================================================
    # WORK CONTEXT
    # =====================================================
    path("work/", views.work_context_list, name="work_context_list"),
    path("work/new/", views.work_context_create, name="work_create"),
    path("work/activate/<uuid:context_id>/", views.work_context_activate, name="work_activate"),


    # =====================================================
    # 📋 SUBMISSIONS (CHECKLIST + DYNAMIC)
    # =====================================================

    # Unified list (replaces ipqc_submission_list_view)
    path(
        "submissions/",
        views.submission_list_view,
        name="submission_list",
    ),

    # Unified detail (CHECKLIST + DYNAMIC)
    path(
        "submissions/<uuid:submission_id>/",
        views.submission_detail_view,
        name="submission_detail",
    ),

    # =====================================================
    # 📊 IPQC DASHBOARD (CHECKLIST + DYNAMIC)
    # =====================================================

    path(
        "ipqc/dashboard/",
        views.ipqc_dashboard_view,
        name="ipqc_dashboard",
    ),

    # =====================================================
    # 🎯 ROLE-BASED DASHBOARD
    # =====================================================
    path(
        "dashboard/",
        views.dashboard_view,
        name="dashboard",
    ),

    # =====================================================
    # 🔔 NOTIFICATIONS
    # =====================================================
    path(
        "notifications/",
        views.notification_list_view,
        name="notification_list",
    ),


    # ✅ POPUP VIEW
    path(
        "submission/view/<uuid:submission_id>/",
        views.submission_detail_popup,
        name="submission_popup",
    ),
    
    path(
        "dynamic/popup/<uuid:submission_id>/",
        views.dynamic_submission_detail_popup,
        name="dynamic_submission_popup",
    ),

    path(
        "ipqc/dashboard/",
        views.ipqc_dashboard_view,
        name="ipqc_dashboard",
    ),


    # =====================================================
    # PQE
    # =====================================================
    path(
        "pqe/review/<uuid:submission_id>/",
        views.pqe_review_and_approve,
        name="pqe_review_popup",
    ),

    path(
        "approvals/pending/",
        views.approval_pending_dashboard,
        name="approval_pending_dashboard",
    ),

    path(
        "approvals/approve/<uuid:submission_id>/",
        views.approve_submission,
        name="approve_submission",
    ),


    path(
        "public/submission/view/<uuid:token>/",
        views.public_submission_popup,
        name="public_submission_popup",
    ),

    path("public-approval/<str:token>/<str:category_code>/", views.public_role_approval, name="public_role_approval"),
    path(
        "public-dynamic-approval/<str:token>/<str:category_code>/",
        views.public_dynamic_role_approval,
        name="public_dynamic_role_approval",
    ),
    path(
        "public-dynamic-submission/<str:token>/",
        views.public_dynamic_submission_popup,
        name="public_dynamic_submission_popup",
    ),
]
