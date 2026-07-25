from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseForbidden

from core.identity.models import Permission, RolePermission
from core.identity.permissions import has_permission


@login_required
def permission_master_list(request):
    if not has_permission(request.user, "can_manage_users"):
        return HttpResponseForbidden()

    permissions = (
        Permission.objects
        .all()
        .prefetch_related("permission_roles__role")
    )

    return render(request, "identity/permission_master_list.html", {
        "permissions": permissions
    })


@login_required
def permission_delete(request, permission_id):
    if not has_permission(request.user, "can_manage_users"):
        return HttpResponseForbidden()

    permission = get_object_or_404(Permission, id=permission_id)

    if request.method == "POST":
        # remove mappings first (safe)
        RolePermission.objects.filter(permission=permission).delete()
        permission.delete()
        return redirect("identity:permission_master_list")

    return render(request, "identity/confirm_delete.html", {
        "title": "Delete Permission",
        "object": permission,
        "cancel_url": "identity:permission_master_list",
    })