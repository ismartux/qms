from django.db import transaction
from django.db.models import Q
from django.core.cache import cache
from forms_engine.models import ChecklistTemplate, ChecklistVersion
from core.identity.models import UserScope


# =====================================================
# VERSION ACTIVATION
# =====================================================

def activate_new_version(template: ChecklistTemplate):
    with transaction.atomic():

        versions = (
            ChecklistVersion.objects
            .select_for_update()
            .filter(template_id=template.id)
        )

        if not versions.exists():
            raise ValueError("No versions found for template")

        # Deactivate all first
        versions.update(is_active=False)

        latest_version = versions.order_by("-version_number").first()

        if not latest_version:
            raise ValueError("No version available to activate")

        latest_version.is_active = True
        latest_version.is_published = True
        latest_version.save(update_fields=["is_active", "is_published"])

        template.is_active = True
        template.save(update_fields=["is_active"])

        # 🔥 IMPORTANT: Clear cache when activating new version
        cache.delete_pattern(f"applicable_templates:*")

        return latest_version

# =====================================================
# TEMPLATE RESOLUTION (CORE LOGIC)
# =====================================================

CACHE_TIMEOUT = 300  # 5 minutes (tune based on business needs)


def get_applicable_templates(work_context):

    if (
        not work_context
        or not work_context.plant_id
        or not work_context.product_id
    ):
        return ChecklistTemplate.objects.none()

    user = work_context.user
    plant_id = work_context.plant_id
    product_id = work_context.product_id

    # -------------------------------------------------
    # USER SCOPE FIRST (Needed for cache key)
    # -------------------------------------------------
    if user.is_superuser:
        department_id = "all"
        role_id = "all"
    else:
        user_scope = (
            UserScope.objects
            .select_related("department", "role")
            .filter(user_id=user.id, plant_id=plant_id)
            .first()
        )

        if not user_scope:
            return ChecklistTemplate.objects.none()

        department_id = user_scope.department_id
        role_id = user_scope.role_id

    # -------------------------------------------------
    # ROLE-AWARE CACHE KEY (NO USER ID)
    # -------------------------------------------------
    cache_key = (
        f"applicable_templates:"
        f"plant:{plant_id}:"
        f"product:{product_id}:"
        f"dept:{department_id}:"
        f"role:{role_id}"
    )

    cached_ids = cache.get(cache_key)
    if cached_ids is not None:
        return ChecklistTemplate.objects.filter(id__in=cached_ids)

    # -------------------------------------------------
    # BASE FILTER (INDEXED)
    # -------------------------------------------------
    qs = ChecklistTemplate.objects.filter(
        is_active=True,
        is_archived=False,
        plants__id=plant_id,
    )

    # -------------------------------------------------
    # PRODUCT FILTER (MORE OPTIMAL)
    # -------------------------------------------------
    product_specific = qs.filter(products__id=product_id)
    product_global = qs.filter(products__isnull=True)
    qs = (product_specific | product_global)

    # -------------------------------------------------
    # ROLE / DEPARTMENT FILTER
    # -------------------------------------------------
    if not user.is_superuser:
        qs = qs.filter(department_id=department_id)
        qs = qs.filter(role_assignments__role_id=role_id)

    qs = qs.distinct()

    # -------------------------------------------------
    # CACHE IDS ONLY
    # -------------------------------------------------
    template_ids = list(qs.values_list("id", flat=True))
    cache.set(cache_key, template_ids, CACHE_TIMEOUT)

    return ChecklistTemplate.objects.filter(id__in=template_ids)