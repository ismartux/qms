from django.shortcuts import render, redirect, get_object_or_404
from django.db import models, transaction
from django.views.decorators.http import require_POST
from django.contrib import messages
from django.core.exceptions import ValidationError, PermissionDenied

from core.identity.permissions import has_permission
from ehs_engine.models import EHSFormVersion, EHSFormTemplate


# =========================================================
# CREATE VERSION
# =========================================================

def version_create(request, template_id):

    # 🔐 Permission check
    if not has_permission(request.user, "can_manage_ehs_templates"):
        raise PermissionDenied("You do not have permission to manage EHS versions.")

    template = get_object_or_404(EHSFormTemplate, pk=template_id)

    if template.is_archived:
        messages.error(request, "Cannot create version for archived template.")
        return redirect("ehs_builder:template_list")

    next_version = (
        template.versions.aggregate(
            models.Max("version_number")
        )["version_number__max"] or 0
    ) + 1

    version = EHSFormVersion.objects.create(
        template=template,
        version_number=next_version,
        is_active=False,
        is_published=False,
    )

    messages.success(request, f"Version v{next_version} created.")
    return redirect("ehs_builder:version_edit", pk=version.pk)


# =========================================================
# EDIT VERSION
# =========================================================

def version_edit(request, pk):

    # 🔐 Permission check
    if not has_permission(request.user, "can_manage_ehs_templates"):
        raise PermissionDenied("You do not have permission to edit EHS versions.")

    version = get_object_or_404(
        EHSFormVersion.objects.prefetch_related("sections__items"),
        pk=pk
    )

    template = version.template

    if request.method == "POST":

        try:
            publish_requested = "is_published" in request.POST
            activate_requested = "is_active" in request.POST

            with transaction.atomic():

                # =====================================================
                # PUBLISH LOGIC
                # =====================================================

                if publish_requested and not version.is_published:

                    # Ensure at least one section exists
                    if not version.sections.exists():
                        raise ValidationError(
                            "Cannot publish version without sections."
                        )

                    # Ensure at least one item exists
                    has_items = any(
                        section.items.exists()
                        for section in version.sections.all()
                    )

                    if not has_items:
                        raise ValidationError(
                            "Cannot publish version without items."
                        )

                    # Unpublish other versions
                    EHSFormVersion.objects.filter(
                        template=template,
                        is_published=True
                    ).exclude(pk=version.pk).update(is_published=False)

                    version.is_published = True
                    messages.success(request, "Version published successfully.")

                # If unchecking publish
                if not publish_requested and version.is_published:
                    if version.is_active:
                        raise ValidationError(
                            "Deactivate version before unpublishing."
                        )
                    version.is_published = False
                    messages.success(request, "Version unpublished.")

                # =====================================================
                # ACTIVATE LOGIC
                # =====================================================

                if activate_requested:

                    if not version.is_published:
                        raise ValidationError(
                            "Only published version can be activated."
                        )

                    # Deactivate other active versions
                    EHSFormVersion.objects.filter(
                        template=template,
                        is_active=True
                    ).exclude(pk=version.pk).update(is_active=False)

                    version.is_active = True
                    messages.success(request, "Version activated.")

                # If unchecking active
                if not activate_requested and version.is_active:
                    version.is_active = False
                    messages.success(request, "Version deactivated.")

                version.save()

        except ValidationError as e:
            messages.error(request, e)

        except Exception as e:
            messages.error(request, f"Error updating version: {str(e)}")

    return render(
        request,
        "ehs_engine/builder/version_edit.html",
        {
            "version": version,
        }
    )


# =========================================================
# DELETE VERSION
# =========================================================

@require_POST
def version_delete(request, pk):

    # 🔐 Permission check
    if not has_permission(request.user, "can_manage_ehs_templates"):
        raise PermissionDenied("You do not have permission to delete EHS versions.")

    version = get_object_or_404(EHSFormVersion, pk=pk)
    template_id = version.template.id

    if version.is_published:
        messages.error(request, "Cannot delete a published version.")
        return redirect("ehs_builder:template_edit", pk=template_id)

    if version.is_active:
        messages.error(request, "Cannot delete an active version.")
        return redirect("ehs_builder:template_edit", pk=template_id)

    version.delete()
    messages.success(request, "Version deleted successfully.")

    return redirect("ehs_builder:template_edit", pk=template_id)