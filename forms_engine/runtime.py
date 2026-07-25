from django.core.exceptions import ObjectDoesNotExist
from django.core.exceptions import PermissionDenied

from forms_engine.models import (
    ChecklistTemplate,
    ChecklistVersion,
)

from core.tenant.context import get_current_plant


# =====================================================
# ACTIVE TEMPLATE RESOLUTION (PLANT-SAFE)
# =====================================================

def get_active_template(code: str) -> ChecklistVersion:
    """
    Return active ChecklistVersion for a given template code.
    Fully plant-isolated.
    """

    plant = get_current_plant()

    if plant is None:
        raise PermissionDenied("Plant context not set")

    try:
        template = (
            ChecklistTemplate.objects
            .filter(
                code=code,
                is_active=True,
                is_archived=False,
                plants=plant,  # 🔐 enforce plant isolation
            )
            .distinct()
            .get()
        )
    except ChecklistTemplate.DoesNotExist:
        raise ValueError(f"Active template not found for code: {code}")

    try:
        return (
            ChecklistVersion.objects
            .select_related("template")
            .get(
                template=template,
                is_active=True,
                is_published=True
            )
        )
    except ChecklistVersion.DoesNotExist:
        raise ValueError(
            f"No active version found for template: {template.code}"
        )


# =====================================================
# RUNTIME SCHEMA COMPILATION
# =====================================================

def compile_runtime_schema(version: ChecklistVersion) -> dict:
    """
    Compile checklist version into runtime-safe JSON schema.
    Plant isolation already enforced upstream.
    """

    version = (
        ChecklistVersion.objects
        .select_related("template")
        .prefetch_related(
            "sections__items__rules",
            "sections__items__options",
        )
        .get(pk=version.pk)
    )

    schema = {
        "template": version.template.code,
        "version": version.version_number,
        "sections": [],
    }

    for section in version.sections.all():
        section_data = {
            "title": section.title,
            "items": [],
        }

        for item in section.items.all():
            item_data = {
                "item_id": item.item_id,
                "label": item.label,
                "type": item.item_type,
                "required": item.required,
                "severity_weight": item.severity_weight,
                "rules": [
                    {
                        "type": rule.rule_type,
                        "condition": rule.condition_value,
                    }
                    for rule in item.rules.all()
                ],
            }

            if item.item_type == "DROPDOWN":
                item_data["options"] = [
                    {
                        "label": opt.label,
                        "value": opt.value,
                    }
                    for opt in item.options.all()
                ]

            section_data["items"].append(item_data)

        schema["sections"].append(section_data)

    return schema