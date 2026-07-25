from django.shortcuts import render, redirect, get_object_or_404
from django.views.decorators.http import require_POST
from django.contrib import messages
from django.db import transaction, models
from django.core.exceptions import ValidationError, PermissionDenied

from core.identity.permissions import has_permission
from ehs_engine.models import EHSSection, EHSFormVersion


# =========================================================
# CREATE SECTION
# =========================================================

def section_create(request, version_id):

    # 🔐 Permission check
    if not has_permission(request.user, "can_manage_ehs_templates"):
        raise PermissionDenied("You do not have permission to manage EHS templates.")

    version = get_object_or_404(EHSFormVersion, pk=version_id)

    # 🔒 Prevent modification if version is published or active
    if version.is_published or version.is_active:
        messages.error(
            request,
            "Cannot modify a published or active version."
        )
        return redirect("ehs_builder:version_edit", pk=version.pk)

    if request.method == "POST":
        try:
            title = request.POST.get("title", "").strip()
            order_value = request.POST.get("order")

            if not title:
                raise ValidationError("Section title is required.")

            # Auto assign next order if not provided
            if not order_value:
                max_order = version.sections.aggregate(
                    max_order=models.Max("order")
                )["max_order"] or 0
                order = max_order + 1
            else:
                order = int(order_value)

            with transaction.atomic():
                EHSSection.objects.create(
                    version=version,
                    title=title,
                    order=order,
                )

            messages.success(request, "Section created successfully.")

        except ValidationError as e:
            messages.error(request, e)

        except Exception as e:
            messages.error(request, f"Error creating section: {str(e)}")

        return redirect("ehs_builder:version_edit", pk=version.pk)

    return render(
        request,
        "ehs_engine/builder/section_form.html",
        {
            "version": version
        }
    )


# =========================================================
# EDIT SECTION
# =========================================================

def section_edit(request, pk):

    # 🔐 Permission check
    if not has_permission(request.user, "can_manage_ehs_templates"):
        raise PermissionDenied("You do not have permission to manage EHS templates.")

    section = get_object_or_404(EHSSection, pk=pk)
    version = section.version

    # 🔒 Prevent modification if version is published or active
    if version.is_published or version.is_active:
        messages.error(
            request,
            "Cannot modify a published or active version."
        )
        return redirect("ehs_builder:version_edit", pk=version.pk)

    if request.method == "POST":
        try:
            title = request.POST.get("title", "").strip()
            order_value = request.POST.get("order")

            if not title:
                raise ValidationError("Section title is required.")

            section.title = title
            section.order = int(order_value) if order_value else section.order

            section.full_clean()
            section.save()

            messages.success(request, "Section updated successfully.")

        except ValidationError as e:
            messages.error(request, e)

        except Exception as e:
            messages.error(request, f"Error updating section: {str(e)}")

        return redirect("ehs_builder:version_edit", pk=version.pk)

    return render(
        request,
        "ehs_engine/builder/section_form.html",
        {
            "section": section,
            "version": version,
        }
    )


# =========================================================
# DELETE SECTION
# =========================================================

@require_POST
def section_delete(request, pk):

    # 🔐 Permission check
    if not has_permission(request.user, "can_manage_ehs_templates"):
        raise PermissionDenied("You do not have permission to manage EHS templates.")

    section = get_object_or_404(EHSSection, pk=pk)
    version = section.version

    # 🔒 Prevent deletion if version is published or active
    if version.is_published or version.is_active:
        messages.error(
            request,
            "Cannot delete section from a published or active version."
        )
        return redirect("ehs_builder:version_edit", pk=version.pk)

    version_id = version.pk

    try:
        with transaction.atomic():
            section.delete()

        messages.success(request, "Section deleted successfully.")

    except Exception as e:
        messages.error(request, f"Error deleting section: {str(e)}")

    return redirect("ehs_builder:version_edit", pk=version_id)