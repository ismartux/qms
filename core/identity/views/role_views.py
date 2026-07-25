from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseForbidden

from core.identity.models import Role, Permission, RolePermission
from core.identity.permissions import has_permission


@login_required
def permission_list(request):
    if not has_permission(request.user, "can_manage_users"):
        return HttpResponseForbidden()

    roles = Role.objects.all()
    return render(request, "identity/role_list.html", {
        "roles": roles,
    })


@login_required
def permission_create(request):
    if not has_permission(request.user, "can_manage_users"):
        return HttpResponseForbidden()

    if request.method == "POST":
        Role.objects.create(
            code=request.POST["code"],
            name=request.POST["name"],
            is_active=bool(request.POST.get("is_active")),
        )
        return redirect("identity:permission_list")

    return render(request, "identity/role_form.html")


@login_required
def role_permissions(request, role_id):
    if not has_permission(request.user, "can_manage_users"):
        return HttpResponseForbidden()

    role = get_object_or_404(Role, id=role_id)
    permissions = Permission.objects.filter(is_active=True)

    if request.method == "POST":
        RolePermission.objects.filter(role=role).delete()

        selected = request.POST.getlist("permissions")
        RolePermission.objects.bulk_create([
            RolePermission(role=role, permission_id=pid)
            for pid in selected
        ])

        return redirect("identity:permission_list")

    assigned = set(
        role.role_permissions.values_list("permission_id", flat=True)
    )

    return render(request, "identity/role_permissions.html", {
        "role": role,
        "permissions": permissions,
        "assigned": assigned,
    })