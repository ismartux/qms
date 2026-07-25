# dynamic_forms/admin_views/urls.py

from django.urls import path
from dynamic_forms.admin_views import views

app_name = "dynamic_forms_admin"

urlpatterns = [
    # ===============================
    # TEMPLATE
    # ===============================
    path(
        "",
        views.template_list,
        name="template_list",
    ),
    path(
        "create/",
        views.template_create,
        name="template_create",
    ),
    path(
        "<uuid:template_id>/",
        views.template_detail,
        name="template_detail",
    ),

    # ===============================
    # VERSION
    # ===============================
    path(
        "<uuid:template_id>/versions/create/",
        views.version_create,
        name="version_create",
    ),
    path(
        "version/<int:version_id>/builder/",
        views.form_builder,
        name="form_builder",
    ),
    path(
        "version/<int:version_id>/preview/",
        views.form_preview,
        name="form_preview",
    ),
    path(
        "version/<int:version_id>/save/",
        views.save_builder_config,
        name="save_builder_config",
    ),
    path(
        "version/<int:version_id>/edit/",
        views.version_edit,
        name="version_edit",
    ),
    path(
        "version/<int:version_id>/delete/",
        views.version_delete,
        name="version_delete",
    ),
]