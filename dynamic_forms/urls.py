from django.urls import path
from dynamic_forms import views

app_name = "dynamic_forms"

urlpatterns = [
    path("", views.form_list, name="form_list"),
    path("<uuid:template_id>/", views.form_open, name="form_open"),

    # 🔥 ADD THIS LINE (FIXES YOUR ERROR)
    path(
        "<uuid:template_id>/resolve-dependency/",
        views.resolve_field_dependency,
        name="resolve_field_dependency",
    ),

    path("save/<uuid:submission_id>/", views.form_save, name="form_save"),
    path("submit/<uuid:submission_id>/", views.form_submit, name="form_submit"),
]