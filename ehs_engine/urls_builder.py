from django.urls import path
from .admin_views import template_views, version_views, section_views, item_views

app_name = "ehs_builder"

urlpatterns = [

    # Template
    path("templates/", template_views.template_list, name="template_list"),
    path("templates/create/", template_views.template_create, name="template_create"),
    path("templates/<int:pk>/edit/", template_views.template_edit, name="template_edit"),

    # Version
    path("templates/<int:template_id>/versions/create/", version_views.version_create, name="version_create"),
    path("versions/<int:pk>/edit/", version_views.version_edit, name="version_edit"),

    # Section
    path("versions/<int:version_id>/sections/create/", section_views.section_create, name="section_create"),
    path("sections/<int:pk>/edit/", section_views.section_edit, name="section_edit"),

    # Item
    path("sections/<int:section_id>/items/create/", item_views.item_create, name="item_create"),
    path("items/<int:pk>/edit/", item_views.item_edit, name="item_edit"),
    
    # Version
    path("versions/<int:pk>/delete/", version_views.version_delete, name="version_delete"),

    # Section
    path("sections/<int:pk>/delete/", section_views.section_delete, name="section_delete"),

    # Item
    path("items/<int:pk>/delete/", item_views.item_delete, name="item_delete"),
]