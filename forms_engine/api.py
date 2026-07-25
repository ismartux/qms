from django.http import JsonResponse
from django.views.decorators.http import require_GET
from django.contrib.auth.decorators import login_required
from django.core.cache import cache

from forms_engine.runtime import (
    get_active_template,
    compile_runtime_schema,
)
from forms_engine.services import get_applicable_templates


@require_GET
@login_required
def form_schema_api(request, code):
    """
    Return runtime schema for a checklist template.

    Enforces:
    - authenticated user
    - active work context
    - template applicability
    - plant isolation
    - version-safe caching
    """

    user = request.user

    # -------------------------------------------------
    # WORK CONTEXT VALIDATION
    # -------------------------------------------------
    work_context = getattr(user, "active_work_context", None)

    if not work_context:
        return JsonResponse(
            {"error": "Active work context not set"},
            status=400
        )

    plant = work_context.plant

    # -------------------------------------------------
    # TEMPLATE APPLICABILITY RESOLUTION
    # -------------------------------------------------
    applicable_templates = get_applicable_templates(work_context)

    template = (
        applicable_templates
        .filter(code=code)
        .select_related("department")
        .first()
    )

    if not template:
        return JsonResponse(
            {"error": "Template not applicable for current context"},
            status=403
        )

    # -------------------------------------------------
    # ACTIVE VERSION RESOLUTION
    # -------------------------------------------------
    try:
        version = get_active_template(template.code)
    except ValueError as e:
        return JsonResponse(
            {"error": str(e)},
            status=404
        )

    # -------------------------------------------------
    # SAFE CACHE KEY (PLANT + VERSION AWARE)
    # -------------------------------------------------
    cache_key = (
        f"form_schema:"
        f"plant:{plant.id}:"
        f"template:{template.code}:"
        f"version:{version.version_number}"
    )

    cached_schema = cache.get(cache_key)
    if cached_schema:
        return JsonResponse(cached_schema, safe=True)

    # -------------------------------------------------
    # COMPILE RUNTIME SCHEMA
    # -------------------------------------------------
    schema = compile_runtime_schema(version)

    # -------------------------------------------------
    # CACHE (5 minutes)
    # -------------------------------------------------
    cache.set(cache_key, schema, timeout=300)

    return JsonResponse(schema, safe=True)