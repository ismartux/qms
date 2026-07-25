from django.urls import path
from core.identity.views.role_views import (
    permission_list,
    permission_create,
    role_permissions,
)
from core.identity.views.permission_views import permission_delete, permission_master_list

app_name = "identity"

urlpatterns = [
    # ===============================
    # PERMISSION GROUPS (Role model)
    # ===============================
    path("", permission_list, name="permission_list"),
    path("permissions/create/", permission_create, name="permission_create"),
    path(
        "permissions/<int:role_id>/assign/",
        role_permissions,
        name="permission_assign",
    ),

    # ===============================
    # MASTER PERMISSIONS
    # ===============================
    path(
        "permission-master/",
        permission_master_list,
        name="permission_master_list",
    ),
    
    path(
        "permission-master/<int:permission_id>/delete/",
        permission_delete,
        name="permission_delete",
    ),
]