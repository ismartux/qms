"""
Assignment resolver service for QMS.
Handles resolution of:
- Shop-wise PQE assignments
- Floor-wise TL assignments
- IPQC user mappings
- Contextual TL and PQE resolution for submissions and work contexts
"""

from typing import List, Optional, Tuple, Dict, Any
from django.contrib.auth import get_user_model
from org.models import (
    Floor,
    Shop,
    Line,
    FloorTLAssignment,
    ShopPQEAssignment,
    IPQCMapping,
)

User = get_user_model()


def get_active_tls_for_floor(floor: Optional[Floor], shift: Optional[str] = None) -> List[Any]:
    """
    Returns list of active TL users assigned to a given floor and shift.
    """
    if not floor:
        return []
    
    qs = FloorTLAssignment.objects.filter(floor=floor, is_active=True).select_related("user")
    if shift and shift != "ALL":
        qs = qs.filter(shift__in=[shift, "ALL"])
    
    return [assignment.user for assignment in qs]


def get_active_pqes_for_shop(shop: Optional[Shop]) -> List[Any]:
    """
    Returns list of active PQE users assigned to a given shop.
    """
    if not shop:
        return []
    
    qs = ShopPQEAssignment.objects.filter(shop=shop, is_active=True).select_related("user")
    return [assignment.user for assignment in qs]


def get_ipqc_mapping_for_user(user, plant=None) -> Optional[IPQCMapping]:
    """
    Returns active IPQC mapping for a given user.
    """
    if not user or not user.is_authenticated:
        return None
    
    qs = IPQCMapping.objects.filter(user=user, is_active=True).select_related(
        "plant", "floor", "shop"
    ).prefetch_related("lines")
    
    if plant:
        qs = qs.filter(plant=plant)
        
    return qs.first()


def resolve_submission_assignments(submission) -> Dict[str, Any]:
    """
    Resolves the Floor, Shop, mapped TLs, and mapped PQEs for a given submission.
    """
    floor = getattr(submission, "floor", None)
    shop = getattr(submission, "shop", None)
    line = getattr(submission, "line", None)
    work_context = getattr(submission, "work_context", None)
    shift = getattr(work_context, "shift", None) if work_context else None

    # Fallback to line's floor/shop if not directly set on submission
    if not floor and line and hasattr(line, "floor") and line.floor:
        floor = line.floor
    if not shop and line and hasattr(line, "shop") and line.shop:
        shop = line.shop

    # Fallback to work_context floor/shop if not set
    if not floor and work_context and hasattr(work_context, "floor") and work_context.floor:
        floor = work_context.floor
    if not shop and work_context and hasattr(work_context, "shop") and work_context.shop:
        shop = work_context.shop

    # Fallback to submitter's IPQCMapping if still not resolved
    if (not floor or not shop) and getattr(submission, "submitted_by", None):
        mapping = get_ipqc_mapping_for_user(submission.submitted_by)
        if mapping:
            if not floor:
                floor = mapping.floor
            if not shop:
                shop = mapping.shop

    tls = get_active_tls_for_floor(floor, shift=shift)
    pqes = get_active_pqes_for_shop(shop)

    return {
        "floor": floor,
        "shop": shop,
        "floor_name": floor.name if floor else "-",
        "shop_name": shop.name if shop else "-",
        "tls": tls,
        "pqes": pqes,
        "tl_names": ", ".join([u.get_full_name() or u.username for u in tls]) if tls else "-",
        "pqe_names": ", ".join([u.get_full_name() or u.username for u in pqes]) if pqes else "-",
    }


# =========================================================
# PQE SCOPE & AUTHORIZATION ENFORCEMENT
# =========================================================

def is_user_pqe(user) -> bool:
    """
    Returns True if the user has PQE role or is assigned as a PQE in ShopPQEAssignment.
    """
    if not user or not user.is_authenticated:
        return False
    if user.is_superuser:
        return False
    if getattr(user, "scopes", None) and user.scopes.filter(role__code="PQE").exists():
        return True
    if hasattr(user, "employee_profile") and user.employee_profile and user.employee_profile.role and user.employee_profile.role.code == "PQE":
        return True
    if ShopPQEAssignment.objects.filter(user=user, is_active=True).exists():
        return True
    return False


def get_pqe_scope_filters(user) -> Dict[str, Any]:
    """
    Returns dictionary with authorized sets of shop_ids, line_ids, floor_ids, plant_ids, and ipqc_user_ids
    for a given PQE user.
    """
    from django.db.models import Q

    if not user or not user.is_authenticated:
        return {
            "shop_ids": set(),
            "line_ids": set(),
            "floor_ids": set(),
            "plant_ids": set(),
            "ipqc_user_ids": set(),
        }

    # 1. Assigned shops for this PQE
    assigned_shops = Shop.objects.filter(pqe_assignments__user=user, pqe_assignments__is_active=True)
    shop_ids = set(assigned_shops.values_list("id", flat=True))
    plant_ids = set(assigned_shops.values_list("plant_id", flat=True))

    # Also add user's plant scopes from UserScope
    if getattr(user, "scopes", None):
        user_plants = user.scopes.exclude(plant__isnull=True).values_list("plant_id", flat=True)
        plant_ids.update(user_plants)

    # 2. Assigned lines (lines tied to these shops)
    lines = Line.objects.filter(shop_id__in=shop_ids)
    line_ids = set(lines.values_list("id", flat=True))

    # 3. Floors associated with these lines
    floor_ids = set(lines.exclude(floor__isnull=True).values_list("floor_id", flat=True))

    # 4. IPQC mappings tied to these shops or lines
    ipqc_mappings = IPQCMapping.objects.filter(
        Q(shop_id__in=shop_ids) | Q(lines__id__in=line_ids),
        is_active=True,
    ).distinct()
    ipqc_user_ids = set(ipqc_mappings.values_list("user_id", flat=True))
    floor_ids.update(ipqc_mappings.exclude(floor__isnull=True).values_list("floor_id", flat=True))

    return {
        "shop_ids": shop_ids,
        "line_ids": line_ids,
        "floor_ids": floor_ids,
        "plant_ids": plant_ids,
        "ipqc_user_ids": ipqc_user_ids,
    }


def can_pqe_view_or_approve_submission(user, submission) -> bool:
    """
    Validates if a PQE user is authorized to view or approve a given submission.
    - Superusers bypass this check.
    - PQE users can ONLY view/approve submissions for their assigned shop / line / floor / plant / IPQC.
    """
    if not user or not user.is_authenticated:
        return False
    if user.is_superuser:
        return True
    if not is_user_pqe(user):
        return True

    scope = get_pqe_scope_filters(user)

    # If PQE has no assignments, deny
    if not scope["shop_ids"] and not scope["plant_ids"] and not scope["line_ids"]:
        return False

    # 1. Check Plant
    plant_id = getattr(submission, "plant_id", None)
    if not plant_id and getattr(submission, "work_context", None):
        plant_id = submission.work_context.plant_id
    if plant_id and scope["plant_ids"] and plant_id not in scope["plant_ids"]:
        return False

    # 2. Check Shop
    shop_id = getattr(submission, "shop_id", None)
    if not shop_id and getattr(submission, "line", None) and hasattr(submission.line, "shop_id"):
        shop_id = submission.line.shop_id
    if not shop_id and getattr(submission, "work_context", None):
        shop_id = getattr(submission.work_context, "shop_id", None)
        if not shop_id and submission.work_context.line:
            shop_id = getattr(submission.work_context.line, "shop_id", None)

    if scope["shop_ids"]:
        if shop_id:
            return shop_id in scope["shop_ids"]
        
        # If no explicit shop on submission, check line
        line_id = getattr(submission, "line_id", None)
        if not line_id and getattr(submission, "work_context", None):
            line_id = getattr(submission.work_context, "line_id", None)
        if line_id:
            return line_id in scope["line_ids"]

        # If no line, check submitter
        submitter_id = getattr(submission, "submitted_by_id", None)
        if submitter_id and submitter_id in scope["ipqc_user_ids"]:
            return True
        return False

    # 3. Check Line
    line_id = getattr(submission, "line_id", None)
    if not line_id and getattr(submission, "work_context", None):
        line_id = getattr(submission.work_context, "line_id", None)

    if line_id and scope["line_ids"]:
        return line_id in scope["line_ids"]

    # 4. Check IPQC Submitter
    submitter_id = getattr(submission, "submitted_by_id", None)
    if submitter_id and submitter_id in scope["ipqc_user_ids"]:
        return True

    # 5. Check Floor (for floor-level submissions without specific shop/line)
    floor_id = getattr(submission, "floor_id", None)
    if not floor_id and getattr(submission, "work_context", None):
        floor_id = getattr(submission.work_context, "floor_id", None)

    if floor_id and scope["floor_ids"]:
        return floor_id in scope["floor_ids"]

    return False


def filter_submissions_for_pqe_scope(user, qs, is_dynamic=False):
    """
    Filters a Submission or DynamicFormSubmission QuerySet to only include
    submissions matching the PQE user's assigned scope.
    """
    from django.db.models import Q

    if not user or not user.is_authenticated or user.is_superuser or not is_user_pqe(user):
        return qs

    scope = get_pqe_scope_filters(user)
    if not scope["shop_ids"] and not scope["plant_ids"] and not scope["line_ids"]:
        return qs.none()

    q_filter = Q()
    if scope["plant_ids"]:
        if is_dynamic:
            q_filter &= (
                Q(work_context__plant_id__in=scope["plant_ids"]) |
                Q(template_version__template__plants__id__in=scope["plant_ids"])
            )
        else:
            q_filter &= (
                Q(plant_id__in=scope["plant_ids"]) |
                Q(work_context__plant_id__in=scope["plant_ids"])
            )

    scope_matches = Q()
    if scope["shop_ids"]:
        if is_dynamic:
            scope_matches |= (
                Q(work_context__shop_id__in=scope["shop_ids"]) |
                Q(work_context__line__shop_id__in=scope["shop_ids"])
            )
            if scope["ipqc_user_ids"]:
                scope_matches |= (
                    Q(work_context__shop__isnull=True, work_context__line__isnull=True, submitted_by_id__in=scope["ipqc_user_ids"])
                )
        else:
            scope_matches |= (
                Q(shop_id__in=scope["shop_ids"]) |
                Q(line__shop_id__in=scope["shop_ids"]) |
                Q(work_context__shop_id__in=scope["shop_ids"])
            )
            if scope["ipqc_user_ids"]:
                scope_matches |= (
                    Q(shop__isnull=True, line__isnull=True, work_context__shop__isnull=True, submitted_by_id__in=scope["ipqc_user_ids"])
                )

    elif scope["line_ids"]:
        if is_dynamic:
            scope_matches |= Q(work_context__line_id__in=scope["line_ids"])
        else:
            scope_matches |= (
                Q(line_id__in=scope["line_ids"]) |
                Q(work_context__line_id__in=scope["line_ids"])
            )

    elif scope["ipqc_user_ids"]:
        scope_matches |= Q(submitted_by_id__in=scope["ipqc_user_ids"])

    elif scope["floor_ids"]:
        if is_dynamic:
            scope_matches |= (
                Q(work_context__floor_id__in=scope["floor_ids"]) |
                Q(work_context__line__floor_id__in=scope["floor_ids"])
            )
        else:
            scope_matches |= (
                Q(floor_id__in=scope["floor_ids"]) |
                Q(line__floor_id__in=scope["floor_ids"]) |
                Q(work_context__floor_id__in=scope["floor_ids"])
            )

    if scope_matches:
        return qs.filter(q_filter & scope_matches).distinct()
    return qs.filter(q_filter).distinct()


def can_pqe_view_or_approve_capa(user, capa) -> bool:
    """
    Validates if a PQE user is authorized to view, assign, or approve a given CAPA.
    """
    if not user or not user.is_authenticated:
        return False
    if user.is_superuser:
        return True
    if not is_user_pqe(user):
        return True
    if not capa or not getattr(capa, "submission", None):
        return False
    return can_pqe_view_or_approve_submission(user, capa.submission)


def filter_capas_for_pqe_scope(user, qs):
    """
    Filters a CAPA QuerySet to only include CAPAs whose associated submission
    falls strictly within the PQE user's assigned scope (shop/line/floor/plant/IPQC).
    """
    from django.db.models import Q

    if not user or not user.is_authenticated or user.is_superuser or not is_user_pqe(user):
        return qs

    scope = get_pqe_scope_filters(user)
    if not scope["shop_ids"] and not scope["plant_ids"] and not scope["line_ids"]:
        return qs.none()

    q_filter = Q()
    if scope["plant_ids"]:
        q_filter &= (
            Q(submission__plant_id__in=scope["plant_ids"]) |
            Q(submission__work_context__plant_id__in=scope["plant_ids"])
        )

    scope_matches = Q()
    if scope["shop_ids"]:
        scope_matches |= (
            Q(submission__shop_id__in=scope["shop_ids"]) |
            Q(submission__line__shop_id__in=scope["shop_ids"]) |
            Q(submission__work_context__shop_id__in=scope["shop_ids"]) |
            Q(submission__work_context__line__shop_id__in=scope["shop_ids"])
        )
        if scope["ipqc_user_ids"]:
            scope_matches |= (
                Q(
                    submission__shop__isnull=True,
                    submission__line__isnull=True,
                    submission__work_context__shop__isnull=True,
                    submission__work_context__line__isnull=True,
                    submission__submitted_by_id__in=scope["ipqc_user_ids"],
                )
            )

    elif scope["line_ids"]:
        scope_matches |= (
            Q(submission__line_id__in=scope["line_ids"]) |
            Q(submission__work_context__line_id__in=scope["line_ids"])
        )

    elif scope["ipqc_user_ids"]:
        scope_matches |= Q(submission__submitted_by_id__in=scope["ipqc_user_ids"])

    elif scope["floor_ids"]:
        scope_matches |= (
            Q(submission__floor_id__in=scope["floor_ids"]) |
            Q(submission__line__floor_id__in=scope["floor_ids"]) |
            Q(submission__work_context__floor_id__in=scope["floor_ids"])
        )

    if scope_matches:
        return qs.filter(q_filter & scope_matches).distinct()
    return qs.filter(q_filter).distinct()


