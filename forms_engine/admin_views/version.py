from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseForbidden, HttpResponseNotAllowed
from django.db import transaction
from django.db.models import Max

from forms_engine.decorators import admin_required
from forms_engine.models import (
    ChecklistTemplate,
    ChecklistVersion,
    ChecklistSection,
    ChecklistItem,
    ChecklistRule,
)


# =====================================================
# VERSION LIST
# =====================================================
@login_required
@admin_required
def version_list(request, template_id):

    template = get_object_or_404(
        ChecklistTemplate.objects.all(),  # explicit manager
        id=template_id
    )

    versions = (
        ChecklistVersion.objects
        .filter(template=template)
        .order_by("version_number")
    )

    return render(
        request,
        "forms_builder/version_list.html",
        {
            "template": template,
            "versions": versions,
        },
    )


# =====================================================
# CREATE VERSION (AUTO NUMBER, DRAFT)
# =====================================================
@login_required
@admin_required
@transaction.atomic
def create_version(request, template_id):

    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])

    template = get_object_or_404(
        ChecklistTemplate.objects.select_for_update(),
        id=template_id
    )

    last_version = (
        ChecklistVersion.objects
        .filter(template=template)
        .aggregate(max_num=Max("version_number"))
    )["max_num"] or 0

    version = ChecklistVersion.objects.create(
        template=template,
        version_number=last_version + 1,
        is_active=False,
        is_published=False,
    )

    return redirect(
        "transs_admin_flow:manage_sections",
        version_id=version.id
    )


# =====================================================
# CLONE VERSION (PUBLISHED ONLY)
# =====================================================
@login_required
@admin_required
@transaction.atomic
def clone_version(request, version_id):

    source = get_object_or_404(
        ChecklistVersion.objects
        .select_related("template")
        .prefetch_related("sections__items__rules"),
        id=version_id
    )

    if not source.is_published:
        return HttpResponseForbidden(
            "Only published versions can be cloned"
        )

    template = source.template

    last_version = (
        ChecklistVersion.objects
        .filter(template=template)
        .aggregate(max_num=Max("version_number"))
    )["max_num"] or 0

    new_version = ChecklistVersion.objects.create(
        template=template,
        version_number=last_version + 1,
        is_active=False,
        is_published=False,
    )

    # -------------------------------
    # DEEP CLONE STRUCTURE (Optimized)
    # -------------------------------
    for section in source.sections.all():

        new_section = ChecklistSection.objects.create(
            version=new_version,
            title=section.title,
            order=section.order,
        )

        for item in section.items.all():

            new_item = ChecklistItem.objects.create(
                section=new_section,
                item_id=item.item_id,
                label=item.label,
                item_type=item.item_type,
                required=item.required,
                order=item.order,
                severity_weight=item.severity_weight,
            )

            for rule in item.rules.all():
                ChecklistRule.objects.create(
                    item=new_item,
                    rule_type=rule.rule_type,
                    condition_value=rule.condition_value,
                )

    return redirect(
        "transs_admin_flow:manage_sections",
        version_id=new_version.id
    )


# =====================================================
# DELETE VERSION (DRAFT ONLY)
# =====================================================
@login_required
@admin_required
@transaction.atomic
def delete_version(request, version_id):

    version = get_object_or_404(
        ChecklistVersion.objects.select_related("template"),
        id=version_id
    )

    if version.is_published:
        return HttpResponseForbidden(
            "Published version cannot be deleted"
        )

    template_id = version.template.id
    version.delete()

    return redirect(
        "transs_admin_flow:version_list",
        template_id=template_id
    )


# =====================================================
# FINALIZE / PUBLISH VERSION
# =====================================================
@login_required
@admin_required
@transaction.atomic
def finalize_version(request, version_id):

    version = get_object_or_404(
        ChecklistVersion.objects.select_related("template"),
        id=version_id
    )

    template = version.template

    if not version.sections.exists():
        return HttpResponseForbidden(
            "Cannot publish version without sections"
        )

    # Lock template versions to prevent race
    ChecklistVersion.objects.select_for_update().filter(
        template=template
    )

    # Unpublish others
    ChecklistVersion.objects.filter(
        template=template
    ).update(is_active=False, is_published=False)

    version.is_active = True
    version.is_published = True
    version.save(update_fields=["is_active", "is_published"])

    return redirect(
        "transs_admin_flow:form_builder_dashboard"
    )