from django.db.models import Q
from capa.models import CAPA
from submissions.models import Submission, WorkflowState
from core.identity.permissions import has_permission


def global_nav_notifications(request):
    if not request.user.is_authenticated:
        return {}

    user = request.user
    scopes = user.scopes.select_related("plant", "role")

    plant_ids = scopes.values_list("plant_id", flat=True)
    role_ids = scopes.values_list("role_id", flat=True)

    # =========================================================
    # ===================== CAPA BASE =========================
    # =========================================================

    base_capa_qs = CAPA.objects.filter(
        submission__work_context__plant_id__in=plant_ids
    ).exclude(status="CLOSED")

    # =========================================================
    # 🔴 CAPA Approval Pending (Management Only)
    # =========================================================

    approval_count = 0
    can_manage_capa = has_permission(user, "can_manage_capa")

    if can_manage_capa:
        approval_count = base_capa_qs.filter(
            status="ACTION_DONE"
        ).count()

    # =========================================================
    # 🟡 RCA Pending
    # =========================================================

    rca_pending = base_capa_qs.filter(
        rca_role_id__in=role_ids
    ).filter(
        Q(rca_summary__isnull=True) | Q(rca_summary__exact="")
    ).count()

    # =========================================================
    # 🟣 CAPA Pending
    # =========================================================

    capa_pending = base_capa_qs.filter(
        capa_role_id__in=role_ids,
        rca_summary__isnull=False
    ).exclude(
        Q(capa_plan__isnull=False) & ~Q(capa_plan__exact="")
    ).count()

    # =========================================================
    # 🔵 Open CAPA (Management Only)
    # =========================================================

    open_capa_count = 0
    if can_manage_capa:
        open_capa_count = base_capa_qs.filter(
            status="OPEN",
            rca_role__isnull=True,
            capa_role__isnull=True
        ).count()

    # =========================================================
    # 🔥 IPQC FORM APPROVAL PENDING (PQE / ADMIN ONLY)
    # =========================================================

    ipqc_pending_approval_count = 0

    if has_permission(user, "can_approve_ipqc"):

        ipqc_qs = Submission.objects.filter(
            workflow_state=WorkflowState.SUBMITTED,
            plant_id__in=plant_ids,
        ).exclude(
            approvals__isnull=False
        )

        ipqc_pending_approval_count = ipqc_qs.count()

    # =========================================================
    # 🎯 TOTAL NOTIFICATIONS (User Relevant Only)
    # =========================================================

    total_notifications = (
        rca_pending +
        capa_pending
    )

    if can_manage_capa:
        total_notifications += approval_count
        total_notifications += open_capa_count

    if has_permission(user, "can_approve_ipqc"):
        total_notifications += ipqc_pending_approval_count

    return {
        # CAPA
        "approval_count": approval_count,
        "my_pending_rca_count": rca_pending,
        "my_pending_capa_count": capa_pending,
        "open_capa_count": open_capa_count,

        # IPQC
        "ipqc_pending_approval_count": ipqc_pending_approval_count,

        # TOGGLE TOTAL
        "total_notifications": total_notifications,
    }
