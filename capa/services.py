from datetime import timedelta
from django.utils import timezone
from django.utils.timezone import now

from capa.models import CAPA
from core.audit.models import AuditLog




# =========================================================
# CREATE CAPA (MANUAL)
# =========================================================

def create_capa(
    submission,
    title,
    description,
    due_date,
    creator,
):
    """
    Explicit CAPA creation by PQE / Admin.
    """

    capa = CAPA.objects.create(
        submission=submission,
        title=title,
        description=description,
        severity=submission.severity_score,
        due_date=due_date,
        status="OPEN",
    )

    # ---------------- Audit ----------------
    AuditLog.objects.create(
        actor=creator,
        action="CAPA_CREATED",
        object_type="CAPA",
        object_id=str(capa.capa_id),
        metadata={
            "submission_id": str(submission.submission_id),
            "severity": submission.severity_score,
            "mode": "MANUAL",
        },
    )


    return capa


# =========================================================
# AUTO CAPA TRIGGER
# =========================================================

def maybe_trigger_capa(submission):
    """
    Auto-create CAPA based on submission severity.
    """

    print("🧠 maybe_trigger_capa called")

    if submission.severity_score <= 0:
        return

    due_date = timezone.now().date() + timedelta(days=7)

    capa = CAPA.objects.create(
        submission=submission,
        title=f"Auto CAPA for submission {submission.submission_id}",
        description="Automatically generated CAPA due to non-conformance.",
        severity=submission.severity_score,
        due_date=due_date,
        status="OPEN",
    )

    # ---------------- Audit ----------------
    AuditLog.objects.create(
        actor=submission.submitted_by,
        action="CAPA_CREATED",
        object_type="CAPA",
        object_id=str(capa.capa_id),
        metadata={
            "submission_id": str(submission.submission_id),
            "severity": submission.severity_score,
            "mode": "AUTO",
        },
    )


    return capa


# =========================================================
# ASSIGN CAPA
# =========================================================

def assign_capa(capa: CAPA, owner, actor):
    capa.status = "ASSIGNED"
    capa.assigned_by = actor
    capa.save(update_fields=["status", "assigned_by"])

    AuditLog.objects.create(
        actor=actor,
        action="CAPA_ASSIGNED",
        object_type="CAPA",
        object_id=str(capa.capa_id),
        metadata={
            "assigned_to": owner.username if owner else None
        }
    )




# =========================================================
# MARK ACTION DONE
# =========================================================

def mark_action_done(capa: CAPA, actor):
    capa.status = "ACTION_DONE"
    capa.save(update_fields=["status"])

    AuditLog.objects.create(
        actor=actor,
        action="CAPA_ACTION_DONE",
        object_type="CAPA",
        object_id=str(capa.capa_id),
    )



# =========================================================
# CLOSE CAPA (APPROVAL)
# =========================================================

def close_capa(capa: CAPA, actor):
    capa.status = "CLOSED"
    capa.closed_at = now()
    capa.save(update_fields=["status", "closed_at"])

    AuditLog.objects.create(
        actor=actor,
        action="CAPA_CLOSED",
        object_type="CAPA",
        object_id=str(capa.capa_id),
    )



# =========================================================
# REJECT CAPA
# =========================================================

def reject_capa(capa: CAPA, actor, reason: str):

    capa.status = "REJECTED"
    capa.rejection_reason = reason
    capa.rejected_by = actor
    capa.rejected_at = timezone.now()

    # 🔥 Clear action fields
    capa.rca_summary = None
    capa.capa_plan = None

    # 🔥 Clear submission tracking (NEW ADDITION)
    capa.rca_submitted_by = None
    capa.rca_submitted_at = None
    capa.capa_submitted_by = None
    capa.capa_submitted_at = None

    capa.save(update_fields=[
        "status",
        "rejection_reason",
        "rejected_by",
        "rejected_at",
        "rca_summary",
        "capa_plan",
        "rca_submitted_by",
        "rca_submitted_at",
        "capa_submitted_by",
        "capa_submitted_at",
    ])

    AuditLog.objects.create(
        actor=actor,
        action="CAPA_REJECTED",
        object_type="CAPA",
        object_id=str(capa.capa_id),
        metadata={"reason": reason}
    )
