from django.shortcuts import render, redirect, get_object_or_404
from django.views.decorators.http import require_POST
from django.contrib import messages
from django.db import transaction, models
from django.core.exceptions import ValidationError, PermissionDenied

from core.identity.permissions import has_permission
from ehs_engine.models import EHSItem, EHSSection, EHSItemOption


# =========================================================
# CREATE ITEM
# =========================================================

def item_create(request, section_id):

    # 🔐 Permission check
    if not has_permission(request.user, "can_manage_ehs_templates"):
        raise PermissionDenied("You do not have permission to manage EHS templates.")

    section = get_object_or_404(EHSSection, pk=section_id)
    version = section.version

    # 🔒 Prevent editing if version is published or active
    if version.is_published or version.is_active:
        messages.error(request, "Cannot modify published or active version.")
        return redirect("ehs_builder:version_edit", pk=version.pk)

    if request.method == "POST":
        try:
            item_id = request.POST.get("item_id", "").strip()
            label = request.POST.get("label", "").strip()
            item_type = request.POST.get("item_type")
            order_value = request.POST.get("order")
            severity_weight = request.POST.get("severity_weight") or 0

            if not item_id:
                raise ValidationError("Item ID is required.")

            if not label:
                raise ValidationError("Item label is required.")

            # Prevent duplicate item_id in same section
            if section.items.filter(item_id=item_id).exists():
                raise ValidationError("Item ID must be unique within the section.")

            # Auto order if not provided
            if not order_value:
                max_order = section.items.aggregate(
                    max_order=models.Max("order")
                )["max_order"] or 0
                order = max_order + 1
            else:
                order = int(order_value)

            with transaction.atomic():

                item = EHSItem.objects.create(
                    section=section,
                    item_id=item_id,
                    label=label,
                    item_type=item_type,
                    required="required" in request.POST,
                    order=order,
                    require_photo_on_no="require_photo_on_no" in request.POST,
                    require_remark_on_no="require_remark_on_no" in request.POST,
                    escalate_on_no="escalate_on_no" in request.POST,
                    severity_weight=int(severity_weight),
                )

                # Dropdown options
                if item.item_type == "DROPDOWN":
                    options = request.POST.getlist("options")
                    for index, opt in enumerate(options):
                        value = opt.strip()
                        if value:
                            EHSItemOption.objects.create(
                                item=item,
                                label=value,
                                value=value,
                                order=index
                            )

            messages.success(request, "Item created successfully.")

        except ValidationError as e:
            messages.error(request, e)

        except Exception as e:
            messages.error(request, f"Error creating item: {str(e)}")

        return redirect("ehs_builder:version_edit", pk=version.pk)

    return render(
        request,
        "ehs_engine/builder/item_form.html",
        {
            "section": section,
            "item_types": EHSItem.ITEM_TYPES
        }
    )


# =========================================================
# EDIT ITEM
# =========================================================

def item_edit(request, pk):

    # 🔐 Permission check
    if not has_permission(request.user, "can_manage_ehs_templates"):
        raise PermissionDenied("You do not have permission to manage EHS templates.")

    item = get_object_or_404(EHSItem, pk=pk)
    section = item.section
    version = section.version

    # 🔒 Prevent editing if version is published or active
    if version.is_published or version.is_active:
        messages.error(request, "Cannot modify published or active version.")
        return redirect("ehs_builder:version_edit", pk=version.pk)

    if request.method == "POST":
        try:
            label = request.POST.get("label", "").strip()
            item_type = request.POST.get("item_type")
            order_value = request.POST.get("order")
            severity_weight = request.POST.get("severity_weight") or 0

            if not label:
                raise ValidationError("Item label is required.")

            item.label = label
            item.item_type = item_type
            item.required = "required" in request.POST
            item.order = int(order_value) if order_value else item.order
            item.require_photo_on_no = "require_photo_on_no" in request.POST
            item.require_remark_on_no = "require_remark_on_no" in request.POST
            item.escalate_on_no = "escalate_on_no" in request.POST
            item.severity_weight = int(severity_weight)

            with transaction.atomic():
                item.full_clean()
                item.save()

                # Clear options
                item.options.all().delete()

                # Re-add dropdown options if needed
                if item.item_type == "DROPDOWN":
                    options = request.POST.getlist("options")
                    for index, opt in enumerate(options):
                        value = opt.strip()
                        if value:
                            EHSItemOption.objects.create(
                                item=item,
                                label=value,
                                value=value,
                                order=index
                            )

            messages.success(request, "Item updated successfully.")

        except ValidationError as e:
            messages.error(request, e)

        except Exception as e:
            messages.error(request, f"Error updating item: {str(e)}")

        return redirect("ehs_builder:version_edit", pk=version.pk)

    return render(
        request,
        "ehs_engine/builder/item_form.html",
        {
            "item": item,
            "section": section,
            "item_types": EHSItem.ITEM_TYPES,
        }
    )


# =========================================================
# DELETE ITEM
# =========================================================

@require_POST
def item_delete(request, pk):

    # 🔐 Permission check
    if not has_permission(request.user, "can_manage_ehs_templates"):
        raise PermissionDenied("You do not have permission to manage EHS templates.")

    item = get_object_or_404(EHSItem, pk=pk)
    version = item.section.version

    if version.is_published or version.is_active:
        messages.error(request, "Cannot delete item from published or active version.")
        return redirect("ehs_builder:version_edit", pk=version.pk)

    version_id = version.id

    try:
        with transaction.atomic():
            item.delete()

        messages.success(request, "Item deleted successfully.")

    except Exception as e:
        messages.error(request, f"Error deleting item: {str(e)}")

    return redirect("ehs_builder:version_edit", pk=version_id)