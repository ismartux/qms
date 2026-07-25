from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.shortcuts import render, redirect, get_object_or_404
from django.core.exceptions import ValidationError
from forms_engine.decorators import admin_required
from forms_engine.models import (
    ChecklistSection,
    ChecklistItem,
    ChecklistRule,
    ChecklistItemOption
)


# =====================================================
# MANAGE ITEMS
# =====================================================
@login_required
@admin_required
def manage_items(request, section_id):

    section = get_object_or_404(ChecklistSection, id=section_id)
    version = section.version
    template = version.template

    # 🔒 BLOCK IF VERSION IS PUBLISHED
    if version.is_published:
        raise ValidationError("Published versions cannot be modified")

    sections = (
        ChecklistSection.objects
        .filter(version=version)
        .order_by("order")
    )

    if request.method == "POST":
        with transaction.atomic():

            target_section = get_object_or_404(
                ChecklistSection,
                id=request.POST["section"],
                version=version
            )

            order_value = int(request.POST["order"])

            # 🔒 PREVENT DUPLICATE ORDER
            if ChecklistItem.objects.filter(
                section=target_section,
                order=order_value
            ).exists():
                raise ValidationError("Item order already exists in this section")

            item = ChecklistItem.objects.create(
                section=target_section,
                item_id=request.POST["item_id"].strip(),
                label=request.POST["label"].strip(),
                item_type=request.POST["item_type"],
                required=request.POST.get("required") == "on",
                order=order_value,
                severity_weight=int(request.POST.get("severity_weight", 1)),
            )

            # ---------------- RULE (OPTIONAL) ----------------
            rule_type = request.POST.get("rule_type")
            condition_value = request.POST.get("condition_value", "").strip().upper()

            if rule_type and condition_value:
                ChecklistRule.objects.create(
                    item=item,
                    rule_type=rule_type,
                    condition_value=condition_value,
                )

            # ---------------- DROPDOWN OPTIONS ----------------
            if item.item_type == "DROPDOWN":
                option_labels = request.POST.getlist("option_label[]")
                option_values = request.POST.getlist("option_value[]")

                options_to_create = []

                for idx, (label, value) in enumerate(zip(option_labels, option_values)):
                    if label.strip() and value.strip():
                        options_to_create.append(
                            ChecklistItemOption(
                                item=item,
                                label=label.strip(),
                                value=value.strip().upper(),
                                order=idx,
                            )
                        )

                ChecklistItemOption.objects.bulk_create(options_to_create)

        return redirect(
            "transs_admin_flow:manage_items",
            section_id=target_section.id
        )

    return render(
        request,
        "forms_builder/item_manage.html",
        {
            "section": section,
            "sections": sections,
            "items": section.items.order_by("order"),
            "template": template,
            "version": version,
        },
    )


# =====================================================
# EDIT ITEM
# =====================================================
@login_required
@admin_required
def edit_item(request, item_id):

    item = get_object_or_404(ChecklistItem, id=item_id)
    section = item.section
    version = section.version
    template = version.template

    # 🔒 BLOCK IF VERSION IS PUBLISHED
    if version.is_published:
        raise ValidationError("Published versions cannot be modified")

    sections = (
        ChecklistSection.objects
        .filter(version=version)
        .order_by("order")
    )

    rule = item.rules.first()
    options = item.options.all()

    if request.method == "POST":
        with transaction.atomic():

            new_section = get_object_or_404(
                ChecklistSection,
                id=request.POST["section"],
                version=version
            )

            new_order = int(request.POST["order"])

            # 🔒 PREVENT DUPLICATE ORDER (EXCLUDE SELF)
            if ChecklistItem.objects.filter(
                section=new_section,
                order=new_order
            ).exclude(id=item.id).exists():
                raise ValidationError("Item order already exists in this section")

            item.section = new_section
            item.item_id = request.POST["item_id"].strip()
            item.label = request.POST["label"].strip()
            item.item_type = request.POST["item_type"]
            item.required = request.POST.get("required") == "on"
            item.order = new_order
            item.severity_weight = int(request.POST.get("severity_weight", 0))
            item.save()

            # ---------------- RULE HANDLING ----------------
            rule_type = request.POST.get("rule_type")
            condition_value = request.POST.get("condition_value", "").strip().upper()

            if rule_type and condition_value:
                if rule:
                    rule.rule_type = rule_type
                    rule.condition_value = condition_value
                    rule.save()
                else:
                    ChecklistRule.objects.create(
                        item=item,
                        rule_type=rule_type,
                        condition_value=condition_value,
                    )
            else:
                if rule:
                    rule.delete()

            # ---------------- DROPDOWN OPTIONS ----------------
            if item.item_type == "DROPDOWN":
                option_labels = request.POST.getlist("option_label[]")
                option_values = request.POST.getlist("option_value[]")

                ChecklistItemOption.objects.filter(item=item).delete()

                options_to_create = []

                for idx, (label, value) in enumerate(zip(option_labels, option_values)):
                    if label.strip() and value.strip():
                        options_to_create.append(
                            ChecklistItemOption(
                                item=item,
                                label=label.strip(),
                                value=value.strip().upper(),
                                order=idx,
                            )
                        )

                ChecklistItemOption.objects.bulk_create(options_to_create)

        return redirect(
            "transs_admin_flow:manage_items",
            section_id=item.section.id
        )

    return render(
        request,
        "forms_builder/item_edit.html",
        {
            "item": item,
            "sections": sections,
            "rule": rule,
            "options": options,
            "template": template,
            "version": version,
        },
    )


# =====================================================
# DELETE ITEM
# =====================================================
@login_required
@admin_required
def delete_item(request, item_id):

    item = get_object_or_404(ChecklistItem, id=item_id)
    version = item.section.version

    # 🔒 BLOCK IF VERSION IS PUBLISHED
    if version.is_published:
        raise ValidationError("Published versions cannot be modified")

    section_id = item.section.id
    item.delete()

    return redirect(
        "transs_admin_flow:manage_items",
        section_id=section_id
    )