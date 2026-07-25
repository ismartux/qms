from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.http import (
    HttpResponseForbidden,
    JsonResponse,
)
from django.views.decorators.http import require_POST
from django.core.exceptions import ValidationError
from django.contrib import messages
import json

from core.identity.context import get_user_scope

from dynamic_forms.models import (
    DynamicFormTemplate,
    DynamicFormField,
)

from dynamic_forms.services.runtime_engine import (
    DynamicFormRuntimeEngine,
)

from dynamic_forms.services.submission_service import (
    get_or_create_dynamic_form_draft,
    save_dynamic_form_values,
    submit_dynamic_form_submission,
)


# =========================================================
# FORM LIST
# =========================================================

@login_required
def form_list(request):
    scope = get_user_scope(request.user)

    if scope is None and request.user.is_superuser:
        templates = DynamicFormTemplate.objects.filter(
            is_active=True,
            is_archived=False,
        )
    else:
        if not scope:
            templates = DynamicFormTemplate.objects.none()
        else:
            templates = DynamicFormTemplate.objects.filter(
                is_active=True,
                is_archived=False,
                role_assignments__role=scope.role,
            ).distinct()

    return render(
        request,
        "dynamic_forms/runtime/form_list.html",
        {"templates": templates},
    )


# =========================================================
# OPEN FORM
# =========================================================

@login_required
def form_open(request, template_id):

    template = get_object_or_404(
        DynamicFormTemplate,
        id=template_id,
        is_active=True,
        is_archived=False,
    )

    if request.user.is_superuser:
        role = None
    else:
        scope = get_user_scope(request.user)
        if not scope or not scope.role:
            return HttpResponseForbidden(
                "No active role for current plant"
            )
        role = scope.role

    work_context = getattr(request.user, "active_work_context", None)

    try:
        submission = get_or_create_dynamic_form_draft(
            user=request.user,
            template=template,
            role=role,
            work_context=work_context,
        )
    except Exception as e:
        return HttpResponseForbidden(str(e))

    responses = {
        str(v.field_id): v.value
        for v in submission.values.all()
    }

    engine = DynamicFormRuntimeEngine(
        submission.template_version,
        preview=False,
    )
    schema = engine.build_runtime_schema()

    return render(
        request,
        "dynamic_forms/runtime/form_fill.html",
        {
            "template": template,
            "submission": submission,
            "schema": schema,
            "responses": responses,
        },
    )


# =========================================================
# 🔥 DEPENDENCY FILTER ENDPOINT (SINGLE SOURCE)
# =========================================================

@login_required
@require_POST
def resolve_field_dependency(request, template_id):
    """
    AJAX endpoint to resolve:
    - Dependent dropdown options
    - Standard value evaluation

    JSON Payload:
    {
        "field_id": "<field_id>",        // required for dropdown
        "mode": "dropdown" | "standard",
        "responses": {
            "<field_id>": value,
            ...
        }
    }
    """

    template = DynamicFormTemplate.objects.filter(
        id=template_id,
        is_active=True,
        is_archived=False,
    ).first()

    if not template:
        return JsonResponse({"error": "Invalid template"}, status=404)

    version = template.versions.filter(
        is_active=True,
        is_published=True,
    ).first()

    if not version:
        return JsonResponse({"error": "No active version"}, status=400)

    try:
        payload = json.loads(request.body.decode("utf-8"))
    except Exception:
        return JsonResponse({"error": "Invalid JSON"}, status=400)

    mode = payload.get("mode")
    field_id = payload.get("field_id")

    # 🔑 normalize submission context
    responses = {
        str(k): v
        for k, v in (payload.get("responses") or {}).items()
    }

    engine = DynamicFormRuntimeEngine(
        version=version,
        preview=False,
    )

    # 🔥 REQUIRED for dependency + standard rules
    engine._submission_context = responses

    # --------------------------------------------------
    # DROPDOWN DEPENDENCY
    # --------------------------------------------------
    if mode == "dropdown":
        if not field_id:
            return JsonResponse(
                {"error": "field_id required"},
                status=400
            )

        field = DynamicFormField.objects.filter(
            id=field_id,
            version=version,
        ).first()

        if not field:
            return JsonResponse({"options": []})

        options = engine._resolve_dropdown_options(field)
        return JsonResponse({"options": options})

    # --------------------------------------------------
    # STANDARD VALUE RULES
    # --------------------------------------------------
    if mode == "standard":
        results = engine.evaluate_standard_rules(
            submission_values=responses
        )
        return JsonResponse({"results": results})

    return JsonResponse(
        {"error": "Invalid mode"},
        status=400
    )


# =========================================================
# SAVE DRAFT
# =========================================================

@login_required
def form_save(request, submission_id):

    submission = get_object_or_404(
        request.user.dynamic_form_submissions,
        submission_id=submission_id,
    )

    if request.method != "POST":
        return HttpResponseForbidden("Invalid method")

    try:
        save_dynamic_form_values(
            submission=submission,
            payload=request.POST,
        )
        messages.success(request, "Draft saved")
    except ValidationError as e:
        messages.error(request, str(e))

    return redirect(
        "dynamic_forms:form_open",
        template_id=submission.template_version.template.id,
    )


# =========================================================
# SUBMIT FORM
# =========================================================

@login_required
def form_submit(request, submission_id):

    submission = get_object_or_404(
        request.user.dynamic_form_submissions,
        submission_id=submission_id,
    )

    if request.method != "POST":
        return HttpResponseForbidden("Invalid method")

    try:
        save_dynamic_form_values(
            submission=submission,
            payload=request.POST,
        )

        submit_dynamic_form_submission(
            submission=submission,
            user=request.user,
        )

        messages.success(request, "Form submitted successfully")

    except ValidationError as e:
        messages.error(request, str(e))
        return redirect(
            "dynamic_forms:form_open",
            template_id=submission.template_version.template.id,
        )

    return redirect("dynamic_forms:form_list")