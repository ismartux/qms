from django.shortcuts import render, redirect
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.db import transaction
from django.core.cache import cache
import json

from dynamic_forms.admin_views.permissions import require_dynamic_form_builder
from dynamic_forms.admin_views.helpers import (
    get_template_or_404,
    get_version_or_404,
)

from dynamic_forms.models import (
    DynamicFormTemplate,
    DynamicFormVersion,
    DynamicFormField,
    DynamicTemplateRole,
    DynamicFormStandardRule,
    TemplateApprovalStep,
)
from core.identity.models import (
    ApprovalCategory,
)
from core.identity.models import Role
from org.models import Plant, Product, Shop, Department
from dynamic_forms.services.runtime_engine import DynamicFormRuntimeEngine


# =====================================================
# TEMPLATE LIST
# =====================================================
def template_list(request):
    require_dynamic_form_builder(request.user)

    templates = DynamicFormTemplate.objects.filter(is_archived=False)

    return render(
        request,
        "dynamic_forms/admin/template_list.html",
        {"templates": templates},
    )


# =====================================================
# TEMPLATE CREATE
# =====================================================
# =====================================================
# TEMPLATE CREATE (UPDATED – MODEL SAFE)
# =====================================================
@transaction.atomic
def template_create(request):
    require_dynamic_form_builder(request.user)

    context = {
        "plants": Plant.objects.all(),
        "products": Product.objects.all(),
        "shops": Shop.objects.all(),
        "departments": Department.objects.all(),
    }

    if request.method == "POST":

        template = DynamicFormTemplate(
            code=request.POST.get("code"),
            name=request.POST.get("name"),
            description=request.POST.get("description", ""),
            department_id=request.POST.get("department"),

            # Submission structure
            submission_mode=request.POST.get(
                "submission_mode", "AGGREGATED"
            ),

            # Bitable integration
            source_bitable_app_token=request.POST.get(
                "source_bitable_app_token"
            ),
            source_bitable_table_id=request.POST.get(
                "source_bitable_table_id"
            ),
            submission_bitable_app_token=request.POST.get(
                "submission_bitable_app_token"
            ),
            submission_bitable_table_id=request.POST.get(
                "submission_bitable_table_id"
            ),

            is_active=bool(request.POST.get("is_active")),
        )

        # -------------------------------------------------
        # BASE VALIDATION
        # -------------------------------------------------
        template.full_clean()
        template.save()

        # -------------------------------------------------
        # M2M RELATIONS
        # -------------------------------------------------
        template.plants.set(request.POST.getlist("plants"))
        template.products.set(request.POST.getlist("products"))
        template.shops.set(request.POST.getlist("shops"))

        # -------------------------------------------------
        # FINAL VALIDATION (SHOP ↔ PLANT CONSISTENCY)
        # -------------------------------------------------
        template.full_clean()
        template.save()

        return redirect("dynamic_forms_admin:template_list")

    return render(
        request,
        "dynamic_forms/admin/template_create.html",
        context,
    )
    
# =====================================================
# TEMPLATE DETAIL
# =====================================================
def template_detail(request, template_id):
    require_dynamic_form_builder(request.user)

    template = get_template_or_404(template_id)

    # Roles
    roles = Role.objects.filter(is_active=True).order_by("code")
    assignments = {
        a.role_id: a
        for a in template.role_assignments.select_related("role")
    }

    # Approval categories
    categories = ApprovalCategory.objects.filter(is_active=True).order_by("code")
    steps = list(template.approval_steps.select_related("category"))

    if request.method == "POST":

        # -------------------------------
        # SAVE ROLE ASSIGNMENTS
        # -------------------------------
        DynamicTemplateRole.objects.filter(template=template).delete()

        for role in roles:
            if request.POST.get(f"role_{role.id}"):
                DynamicTemplateRole.objects.create(
                    template=template,
                    role=role,
                    requires_work_context=bool(
                        request.POST.get(f"role_{role.id}_requires_context")
                    )
                )

        # -------------------------------
        # SAVE APPROVAL FLOW
        # -------------------------------
        TemplateApprovalStep.objects.filter(template=template).delete()

        order = 1
        for cat in categories:
            if request.POST.get(f"approval_{cat.id}"):

                TemplateApprovalStep.objects.create(
                    template=template,
                    category=cat,
                    order=order,
                    is_required=bool(
                        request.POST.get(f"approval_{cat.id}_required")
                    )
                )
                order += 1

        return redirect(
            "dynamic_forms_admin:template_detail",
            template_id=template.id
        )

    return render(
        request,
        "dynamic_forms/admin/template_detail.html",
        {
            "template": template,
            "roles": roles,
            "assignments": assignments,
            "categories": categories,
            "steps": {s.category_id: s for s in steps},
        },
    )


# =====================================================
# VERSION CREATE
# =====================================================
def version_create(request, template_id):
    require_dynamic_form_builder(request.user)

    template = get_template_or_404(template_id)

    if request.method == "POST":
        version = DynamicFormVersion(
            template=template,
            version_number=int(request.POST.get("version_number")),
            is_active=bool(request.POST.get("is_active")),
            is_published=bool(request.POST.get("is_published")),
        )

        version.full_clean()
        version.save()

        return redirect(
            "dynamic_forms_admin:form_builder",
            version_id=version.id,
        )

    return render(
        request,
        "dynamic_forms/admin/version_create.html",
        {"template": template},
    )


# =====================================================
# FORM BUILDER (OPTIMIZED, NON-BREAKING)
# =====================================================
def form_builder(request, version_id):
    require_dynamic_form_builder(request.user)

    version = get_version_or_404(version_id)

    # Builder does NOT need live Bitable columns
    columns = []

    # -------------------------------------------------
    # EXISTING FIELDS (UNCHANGED, JUST KEPT AS-IS)
    # -------------------------------------------------
    existing_fields = [
        {
            "id": str(field.id),
            "label": field.label,
            "help_text": field.help_text,
            "field_kind": field.field_kind,
            "data_type": field.data_type,
            "bitable_column_id": field.bitable_column_id,
            "required": field.required,
            "order": field.order,

            # 🔑 FIELD DEPENDENCY
            "depends_on_field": (
                str(field.depends_on_field_id)
                if field.depends_on_field_id else None
            ),

            "dropdown_config": field.dropdown_config,
            "number_config": field.number_config,
            "dependency_config": field.dependency_config,
            "reference_config": field.reference_config,
        }
        for field in version.fields.all().order_by("order")
    ]

    # -------------------------------------------------
    # 🔑 EXISTING STANDARD VALUE RULES (THIS WAS MISSING)
    # -------------------------------------------------
    existing_rules = [
        {
            "id": str(rule.id),
            "target_field_id": str(rule.target_field_id),
            "value_source": rule.value_source,
            "manual_value": rule.manual_value,
            "bitable_column_id": rule.bitable_column_id,
            "operator": rule.operator,
            "dependency_filters": rule.dependency_filters,
        }
        for rule in version.standard_rules.all().order_by("created_at")
    ]

    return render(
        request,
        "dynamic_forms/admin/form_builder.html",
        {
            "version": version,
            "columns": columns,
            "existing_fields": existing_fields,

            # 🔑 REQUIRED FOR UI RESTORE
            "existing_rules": existing_rules,
        },
    )
    
def form_preview(request, version_id):
    require_dynamic_form_builder(request.user)

    version = get_version_or_404(version_id)

    engine = DynamicFormRuntimeEngine(version, preview=True)
    schema = engine.build_runtime_schema()

    return render(
        request,
        "dynamic_forms/admin/form_preview.html",
        {"schema": schema},
    )
    
@require_POST
@transaction.atomic
def save_builder_config(request, version_id):
    require_dynamic_form_builder(request.user)

    version = get_version_or_404(version_id)
    payload = json.loads(request.body.decode("utf-8"))

    fields = payload.get("fields", [])
    standard_rules = payload.get("standard_rules", [])

    # ==================================================
    # LOAD EXISTING FIELDS (ID STABILITY GUARANTEE)
    # ==================================================
    existing_fields = {
        str(f.id): f
        for f in DynamicFormField.objects.filter(version=version)
    }

    field_map = {}          # db_id (string) -> DynamicFormField
    used_field_ids = set()  # db ids that remain after save

    # ==================================================
    # PASS 1: CREATE OR UPDATE FIELDS (NO DEPENDENCIES)
    # ==================================================
    for index, field in enumerate(fields):
        db_id = field.get("id")

        if db_id and db_id in existing_fields:
            # ----------------------------
            # UPDATE EXISTING FIELD
            # ----------------------------
            instance = existing_fields[db_id]
            instance.label = field.get("label")
            instance.help_text = field.get("help_text", "")
            instance.field_kind = field.get("field_kind")
            instance.data_type = field.get("data_type")
            instance.bitable_column_id = field.get("bitable_column_id")
            instance.required = field.get("required", False)
            instance.order = index
            instance.dropdown_config = field.get("dropdown_config", {})
            instance.number_config = field.get("number_config", {})
            instance.dependency_config = field.get("dependency_config", {})
            instance.reference_config = field.get("reference_config", {})
            instance.save()

        else:
            # ----------------------------
            # CREATE NEW FIELD
            # ----------------------------
            instance = DynamicFormField.objects.create(
                version=version,
                label=field.get("label"),
                help_text=field.get("help_text", ""),
                field_kind=field.get("field_kind"),
                data_type=field.get("data_type"),
                bitable_column_id=field.get("bitable_column_id"),
                required=field.get("required", False),
                order=index,
                dropdown_config=field.get("dropdown_config", {}),
                number_config=field.get("number_config", {}),
                dependency_config=field.get("dependency_config", {}),
                reference_config=field.get("reference_config", {}),
            )

        field_map[str(instance.id)] = instance
        used_field_ids.add(str(instance.id))

    # ==================================================
    # DELETE REMOVED FIELDS ONLY (SAFE)
    # ==================================================
    for fid, field in existing_fields.items():
        if fid not in used_field_ids:
            field.delete()

    # ==================================================
    # PASS 2: RESOLVE FIELD DEPENDENCIES (FK SAFE)
    # ==================================================
    for field in fields:
        instance = field_map.get(field.get("id"))
        parent_id = field.get("depends_on_field")

        if not instance:
            continue

        if parent_id:
            parent = field_map.get(parent_id)
            instance.depends_on_field = parent
        else:
            instance.depends_on_field = None

        instance.save(update_fields=["depends_on_field"])

    # ==================================================
    # STANDARD RULES (RECREATE — SAFE)
    # ==================================================
    DynamicFormStandardRule.objects.filter(version=version).delete()

    for rule in standard_rules:
        target_field = field_map.get(rule.get("target_field_id"))
        if not target_field:
            continue

        DynamicFormStandardRule.objects.create(
            version=version,
            target_field=target_field,
            value_source=rule.get("value_source"),
            manual_value=rule.get("manual_value"),
            bitable_column_id=rule.get("bitable_column_id"),
            operator=rule.get("operator"),
            dependency_filters=rule.get("dependency_filters", []),
        )

    return JsonResponse({"success": True})

# =====================================================
# VERSION EDIT
# =====================================================
@transaction.atomic
def version_edit(request, version_id):
    require_dynamic_form_builder(request.user)

    version = get_version_or_404(version_id)
    template = version.template

    if request.method == "POST":
        version.version_number = int(request.POST.get("version_number"))
        version.is_active = bool(request.POST.get("is_active"))
        version.is_published = bool(request.POST.get("is_published"))

        version.full_clean()
        version.save()

        return redirect(
            "dynamic_forms_admin:template_detail",
            template_id=template.id,
        )

    return render(
        request,
        "dynamic_forms/admin/version_edit.html",
        {
            "version": version,
            "template": template,
        },
    )
    
# =====================================================
# VERSION DELETE
# =====================================================
@require_POST
@transaction.atomic
def version_delete(request, version_id):
    require_dynamic_form_builder(request.user)

    version = get_version_or_404(version_id)
    template = version.template

    if version.is_published:
        return JsonResponse(
            {"error": "Published version cannot be deleted"},
            status=400,
        )

    if version.is_active:
        return JsonResponse(
            {"error": "Active version cannot be deleted"},
            status=400,
        )

    version.delete()

    return JsonResponse({"success": True})