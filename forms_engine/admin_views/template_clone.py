from django.shortcuts import redirect
from django.http import HttpResponseForbidden
from django.db import transaction, IntegrityError
from django.contrib.auth.decorators import login_required
from django.db.models import Prefetch

from forms_engine.decorators import admin_required
from forms_engine.models import (
    ChecklistTemplate,
    ChecklistVersion,
    ChecklistSection,
    ChecklistItem,
    ChecklistRule,
    ChecklistItemOption,
    TemplateRole,
)


@login_required
@admin_required
@transaction.atomic
def clone_template(request, template_id):

    # -------------------------------------------------
    # FETCH SOURCE TEMPLATE (Plant-aware if middleware applied)
    # -------------------------------------------------
    source_template = (
        ChecklistTemplate.objects
        .prefetch_related(
            "plants",
            "products",
            "shops",
            "role_assignments__role",
            Prefetch(
                "versions",
                queryset=ChecklistVersion.objects
                .filter(is_published=True)
                .order_by("-version_number")
                .prefetch_related(
                    "sections__items__rules",
                    "sections__items__options",
                ),
            ),
        )
        .get(id=template_id)
    )

    # -------------------------------------------------
    # DEPARTMENT VALIDATION
    # -------------------------------------------------
    if not source_template.department_id:
        return HttpResponseForbidden(
            "Cannot clone template without department."
        )

    # -------------------------------------------------
    # SAFE UNIQUE CODE GENERATION (Race Safe)
    # -------------------------------------------------
    base_code = f"{source_template.code}_COPY"
    counter = 0

    while True:
        try:
            new_code = base_code if counter == 0 else f"{base_code}_{counter}"

            new_template = ChecklistTemplate.objects.create(
                code=new_code,
                name=f"{source_template.name} (Copy)",
                description=source_template.description,
                department=source_template.department,
                approval_flow=source_template.approval_flow,
                is_active=False,
                is_archived=False,
                bitable_app_token=source_template.bitable_app_token,
                bitable_table_id=source_template.bitable_table_id,
            )
            break
        except IntegrityError:
            counter += 1

    # -------------------------------------------------
    # COPY SCOPE
    # -------------------------------------------------
    new_template.plants.set(source_template.plants.all())
    new_template.products.set(source_template.products.all())
    new_template.shops.set(source_template.shops.all())

    # -------------------------------------------------
    # COPY ROLE ASSIGNMENTS (BULK)
    # -------------------------------------------------
    TemplateRole.objects.bulk_create([
        TemplateRole(template=new_template, role=role_map.role)
        for role_map in source_template.role_assignments.all()
    ])

    # -------------------------------------------------
    # GET LATEST PUBLISHED VERSION
    # -------------------------------------------------
    source_version = source_template.versions.first()

    if not source_version:
        return redirect(
            "transs_admin_flow:template_detail",
            template_id=new_template.id
        )

    # -------------------------------------------------
    # CREATE NEW DRAFT VERSION
    # -------------------------------------------------
    new_version = ChecklistVersion.objects.create(
        template=new_template,
        version_number=1,
        is_active=False,
        is_published=False,
    )

    # -------------------------------------------------
    # CLONE STRUCTURE SAFELY
    # -------------------------------------------------

    section_map = {}
    item_map = {}

    # ---- Clone Sections
    new_sections = []
    for section in source_version.sections.all():
        new_sections.append(
            ChecklistSection(
                version=new_version,
                title=section.title,
                order=section.order,
            )
        )

    ChecklistSection.objects.bulk_create(new_sections)

    created_sections = ChecklistSection.objects.filter(
        version=new_version
    ).order_by("order")

    for src_section, created_section in zip(
        source_version.sections.all().order_by("order"),
        created_sections
    ):
        section_map[src_section.id] = created_section

    # ---- Clone Items
    new_items = []
    for section in source_version.sections.all():
        for item in section.items.all():
            new_items.append(
                ChecklistItem(
                    section=section_map[section.id],
                    item_id=item.item_id,
                    label=item.label,
                    item_type=item.item_type,
                    required=item.required,
                    order=item.order,
                    severity_weight=item.severity_weight,
                )
            )

    ChecklistItem.objects.bulk_create(new_items)

    created_items = ChecklistItem.objects.filter(
        section__version=new_version
    ).order_by("section__order", "order")

    source_items = [
        item
        for section in source_version.sections.all().order_by("order")
        for item in section.items.all().order_by("order")
    ]

    for src_item, created_item in zip(source_items, created_items):
        item_map[src_item.id] = created_item

    # ---- Clone Rules
    ChecklistRule.objects.bulk_create([
        ChecklistRule(
            item=item_map[item.id],
            rule_type=rule.rule_type,
            condition_value=rule.condition_value,
        )
        for section in source_version.sections.all()
        for item in section.items.all()
        for rule in item.rules.all()
    ])

    # ---- Clone Options
    ChecklistItemOption.objects.bulk_create([
        ChecklistItemOption(
            item=item_map[item.id],
            label=opt.label,
            value=opt.value,
            order=opt.order,
        )
        for section in source_version.sections.all()
        for item in section.items.all()
        for opt in item.options.all()
    ])

    return redirect(
        "transs_admin_flow:manage_sections",
        version_id=new_version.id
    )