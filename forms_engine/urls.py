from django.urls import path

from forms_engine.admin_views.dashboard import dashboard
from forms_engine.admin_views.template import (
    create_template,
    edit_template,
    template_detail,
    archive_template,
)
from forms_engine.admin_views.template_clone import clone_template
from forms_engine.admin_views.version import (
    create_version,
    clone_version,
    delete_version,
    finalize_version,
    version_list,
)
from forms_engine.admin_views.section import (
    manage_sections,
    delete_section,
)
from forms_engine.admin_views.item import (
    manage_items,
    edit_item,
    delete_item,
)
from forms_engine.admin_views.role import assign_roles


app_name = "transs_admin_flow"

urlpatterns = [
    # =================================================
    # DASHBOARD
    # =================================================
    path("", dashboard, name="form_builder_dashboard"),

    # =================================================
    # TEMPLATE
    # =================================================
    path("template/new/", create_template, name="create_template"),
    path("template/<int:template_id>/", template_detail, name="template_detail"),
    path("template/<int:template_id>/edit/", edit_template, name="edit_template"),
    path("template/<int:template_id>/roles/", assign_roles, name="assign_roles"),
    path(
        "template/<int:template_id>/clone/",
        clone_template,
        name="clone_template",
    ),
    path(
        "template/<int:template_id>/archive/",
        archive_template,
        name="archive_template"
    ),

    # =================================================
    # VERSION
    # =================================================
    path(
        "template/<int:template_id>/versions/",
        version_list,
        name="version_list",
    ),
    path(
        "template/<int:template_id>/version/new/",
        create_version,
        name="create_version",
    ),
    path(
        "version/<int:version_id>/clone/",
        clone_version,
        name="clone_version",
    ),
    path(
        "version/<int:version_id>/delete/",
        delete_version,
        name="delete_version",
    ),
    path(
        "version/<int:version_id>/finalize/",
        finalize_version,
        name="finalize_version",
    ),

    # =================================================
    # SECTION
    # =================================================
    path(
        "version/<int:version_id>/sections/",
        manage_sections,
        name="manage_sections",
    ),
    path(
        "section/<int:section_id>/delete/",
        delete_section,
        name="delete_section",
    ),

    # =================================================
    # ITEM
    # =================================================
    path(
        "section/<int:section_id>/items/",
        manage_items,
        name="manage_items",
    ),
    path(
        "item/<int:item_id>/edit/",
        edit_item,
        name="edit_item",
    ),
    path(
        "item/<int:item_id>/delete/",
        delete_item,
        name="delete_item",
    ),
]
