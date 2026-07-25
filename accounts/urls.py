from django.urls import path
from .views import (
                        login_view, 
                        logout_view,
                        user_management,
                        user_create,
                        user_edit,
                        user_created_success,
                        reset_user_password,
                        activate_user,
                        deactivate_user,
                        get_departments,
                        bulk_user_upload,
                        bulk_user_preview,
                        delete_user,
                    )

app_name = "accounts"

urlpatterns = [
    path("login/", login_view, name="login"),
    path("logout/", logout_view, name="logout"),
    path("users/", user_management, name="admin_users"),
    path("users/create/", user_create, name="user_create"),
    path("users/created/", user_created_success, name="user_created_success"),
    path("users/<int:user_id>/delete/", delete_user, name="delete_user"),

    path("users/<int:user_id>/edit/", user_edit, name="user_edit"),
    path("users/<int:user_id>/reset-password/", reset_user_password, name="reset_user_password"),

    path("users/<int:user_id>/activate/", activate_user, name="activate_user"),
    path("users/<int:user_id>/deactivate/", deactivate_user, name="deactivate_user"),
    # AJAX
    path("departments/<int:plant_id>/", get_departments, name="get_departments"),
    
    path("users/bulk-upload/", bulk_user_upload, name="bulk_user_upload"),
    path("users/bulk-preview/", bulk_user_preview, name="bulk_user_preview"),
]