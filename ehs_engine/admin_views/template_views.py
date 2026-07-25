from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.core.exceptions import ValidationError, PermissionDenied
from django.db import IntegrityError

from core.identity.permissions import has_permission
from ehs_engine.models import EHSFormTemplate
from org.models import Plant


# =========================================================
# TEMPLATE LIST
# =========================================================

def template_list(request):

    # 🔐 Permission check (view access)
    if not has_permission(request.user, "can_view_ehs_reports"):
        raise PermissionDenied("You do not have permission to view EHS templates.")

    templates = (
        EHSFormTemplate.objects
        .prefetch_related("plants")
        .order_by("-created_at")
    )

    return render(
        request,
        "ehs_engine/builder/template_list.html",
        {
            "templates": templates
        }
    )


# =========================================================
# CREATE TEMPLATE
# =========================================================

def template_create(request):

    # 🔐 Permission check (manage access)
    if not has_permission(request.user, "can_manage_ehs_templates"):
        raise PermissionDenied("You do not have permission to create EHS templates.")

    if request.method == "POST":

        code = request.POST.get("code", "").strip()
        name = request.POST.get("name", "").strip()
        description = request.POST.get("description", "").strip()
        bitable_app_token = request.POST.get("bitable_app_token", "").strip()
        bitable_table_id = request.POST.get("bitable_table_id", "").strip()
        plant_ids = request.POST.getlist("plants")

        template_type = request.POST.get("template_type", EHSFormTemplate.DAILY)
        recurrence_scope = request.POST.get("recurrence_scope")
        allowed_submissions = request.POST.get("allowed_submissions") or 1

        require_approval = request.POST.get("require_approval") == "true"
        allow_multiple_submissions = request.POST.get("allow_multiple_submissions_per_day") == "true"
        require_incident_reference = request.POST.get("require_incident_reference") == "true"

        if not code or not name:
            messages.error(request, "Code and Name are required.")
            return redirect(request.path)

        try:
            template = EHSFormTemplate.objects.create(
                code=code,
                name=name,
                description=description,
                template_type=template_type,
                recurrence_scope=recurrence_scope if template_type == EHSFormTemplate.DAILY else None,
                allowed_submissions=int(allowed_submissions),
                require_approval=require_approval,
                allow_multiple_submissions_per_day=allow_multiple_submissions,
                require_incident_reference=require_incident_reference,
                is_active=True,
                bitable_app_token=bitable_app_token,
                bitable_table_id=bitable_table_id,
            )

            if plant_ids:
                template.plants.set(plant_ids)

            messages.success(request, "Template created successfully.")
            return redirect("ehs_builder:template_list")

        except IntegrityError:
            messages.error(request, "Template code must be unique.")
            return redirect(request.path)

        except ValidationError as e:
            messages.error(request, e)
            return redirect(request.path)

        except Exception as e:
            messages.error(request, f"Unexpected error: {str(e)}")
            return redirect(request.path)

    return render(
        request,
        "ehs_engine/builder/template_form.html",
        {
            "plants": Plant.objects.select_related("company").all(),
            "has_published_version": False,
            "template_types": EHSFormTemplate.TEMPLATE_TYPE_CHOICES,
            "recurrence_scopes": EHSFormTemplate.RECURRENCE_SCOPE_CHOICES,
        }
    )


# =========================================================
# EDIT TEMPLATE
# =========================================================

def template_edit(request, pk):

    # 🔐 Permission check
    if not has_permission(request.user, "can_manage_ehs_templates"):
        raise PermissionDenied("You do not have permission to edit EHS templates.")

    template = get_object_or_404(
        EHSFormTemplate.objects.prefetch_related("plants"),
        pk=pk
    )

    has_published_version = template.versions.filter(
        is_published=True
    ).exists()

    if request.method == "POST":

        if has_published_version:
            messages.error(
                request,
                "This template cannot be modified because a version is already published."
            )
            return redirect("ehs_builder:template_list")

        try:
            code = request.POST.get("code", "").strip()
            name = request.POST.get("name", "").strip()
            description = request.POST.get("description", "").strip()
            bitable_app_token = request.POST.get("bitable_app_token", "").strip()
            bitable_table_id = request.POST.get("bitable_table_id", "").strip()
            plant_ids = request.POST.getlist("plants")

            template_type = request.POST.get("template_type", EHSFormTemplate.DAILY)
            recurrence_scope = request.POST.get("recurrence_scope")
            allowed_submissions = request.POST.get("allowed_submissions") or 1

            require_approval = request.POST.get("require_approval") == "true"
            allow_multiple_submissions = request.POST.get("allow_multiple_submissions_per_day") == "true"
            require_incident_reference = request.POST.get("require_incident_reference") == "true"

            if not code or not name:
                messages.error(request, "Code and Name are required.")
                return redirect(request.path)

            template.code = code
            template.name = name
            template.description = description
            template.template_type = template_type
            template.recurrence_scope = recurrence_scope if template_type == EHSFormTemplate.DAILY else None
            template.allowed_submissions = int(allowed_submissions)
            template.require_approval = require_approval
            template.allow_multiple_submissions_per_day = allow_multiple_submissions
            template.require_incident_reference = require_incident_reference
            template.bitable_app_token = bitable_app_token
            template.bitable_table_id = bitable_table_id

            template.full_clean()
            template.save()

            template.plants.set(plant_ids)

            messages.success(request, "Template updated successfully.")
            return redirect("ehs_builder:template_list")

        except ValidationError as e:
            messages.error(request, e)
            return redirect(request.path)

        except Exception as e:
            messages.error(request, f"Unexpected error: {str(e)}")
            return redirect(request.path)

    return render(
        request,
        "ehs_engine/builder/template_form.html",
        {
            "template": template,
            "plants": Plant.objects.select_related("company").all(),
            "has_published_version": has_published_version,
            "template_types": EHSFormTemplate.TEMPLATE_TYPE_CHOICES,
            "recurrence_scopes": EHSFormTemplate.RECURRENCE_SCOPE_CHOICES,
        }
    )