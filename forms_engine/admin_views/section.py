from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseForbidden
from django.db import transaction
from django.core.exceptions import ValidationError

from forms_engine.decorators import admin_required
from forms_engine.models import ChecklistVersion, ChecklistSection


# =====================================================
# MANAGE SECTIONS
# =====================================================
@login_required
@admin_required
def manage_sections(request, version_id):

    # 🔒 Select related template to avoid extra query
    version = get_object_or_404(
        ChecklistVersion.objects.select_related("template"),
        id=version_id
    )

    template = version.template

    # 🔒 HARD LOCK: Published versions are immutable
    if version.is_published:
        return HttpResponseForbidden(
            "Published versions cannot be modified."
        )

    # -------------------------------------------------
    # CREATE SECTION
    # -------------------------------------------------
    if request.method == "POST":

        title = request.POST.get("title", "").strip()
        order_raw = request.POST.get("order")

        if not title:
            return HttpResponseForbidden("Section title is required")

        try:
            order = int(order_raw)
        except (TypeError, ValueError):
            return HttpResponseForbidden("Invalid order value")

        with transaction.atomic():
            ChecklistSection.objects.create(
                version=version,
                title=title,
                order=order,
            )

        return redirect(request.path)

    return render(
        request,
        "forms_builder/section_manage.html",
        {
            "version": version,
            "template": template,
            "sections": version.sections.all(),  # ordering already in model
        },
    )


# =====================================================
# DELETE SECTION
# =====================================================
@login_required
@admin_required
def delete_section(request, section_id):

    section = get_object_or_404(
        ChecklistSection.objects.select_related("version__template"),
        id=section_id
    )

    version = section.version

    # 🔒 HARD LOCK: Published versions are immutable
    if version.is_published:
        return HttpResponseForbidden(
            "Published versions cannot be modified."
        )

    version_id = version.id

    section.delete()

    return redirect(
        "transs_admin_flow:manage_sections",
        version_id=version_id
    )