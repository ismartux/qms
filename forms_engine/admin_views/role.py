from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.core.exceptions import PermissionDenied

from forms_engine.decorators import admin_required
from forms_engine.models import ChecklistTemplate, TemplateRole
from core.identity.models import Role
from core.tenant.context import get_current_plant


@login_required
@admin_required
def assign_roles(request, template_id):

    current_plant = get_current_plant()

    # -------------------------------------------------
    # TEMPLATE ACCESS CONTROL
    # -------------------------------------------------
    qs = ChecklistTemplate.objects.prefetch_related(
        "role_assignments__role",
        "plants"
    )

    # 🔒 Enforce plant isolation for non-superusers
    if not request.user.is_superuser:
        if not current_plant:
            raise PermissionDenied("No active plant context")

        qs = qs.filter(plants=current_plant)

    template = get_object_or_404(qs, id=template_id)

    # -------------------------------------------------
    # AVAILABLE ROLES (ACTIVE ONLY)
    # -------------------------------------------------
    available_roles = (
        Role.objects
        .filter(is_active=True)
        .order_by("name")
    )

    # -------------------------------------------------
    # SAVE ROLE ASSIGNMENTS
    # -------------------------------------------------
    if request.method == "POST":

        selected_role_ids = request.POST.getlist("roles")

        valid_roles = Role.objects.filter(
            id__in=selected_role_ids,
            is_active=True
        )

        with transaction.atomic():

            TemplateRole.objects.filter(template=template).delete()

            TemplateRole.objects.bulk_create([
                TemplateRole(template=template, role=role)
                for role in valid_roles
            ])

        return redirect(
            "transs_admin_flow:version_list",
            template_id=template.id
        )

    # -------------------------------------------------
    # CURRENT ASSIGNED ROLES
    # -------------------------------------------------
    assigned_roles = set(
        template.role_assignments.values_list("role_id", flat=True)
    )

    return render(
        request,
        "forms_builder/role_assign.html",
        {
            "template": template,
            "available_roles": available_roles,
            "assigned_roles": assigned_roles,
        },
    )