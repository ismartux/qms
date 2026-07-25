from django.utils.timezone import now
from django.db import transaction
from django.core.exceptions import ValidationError

from core.workflow.models import Approval
from core.audit.models import AuditLog


def request_approval(object_type, object_id, requester):
    """
    Create approval request safely.
    """

    with transaction.atomic():

        approval = Approval.objects.create(
            object_type=object_type,
            object_id=object_id,
            requested_by=requester,
        )

        AuditLog.objects.create(
            actor=requester,
            action="APPROVAL_REQUESTED",
            object_type=object_type,
            object_id=object_id,
        )

    return approval


@transaction.atomic
def approve(approval: Approval, approver, remarks=""):
    """
    Approve safely with row-level locking and state validation.
    """

    # 🔒 Lock row
    approval = (
        Approval.objects
        .select_for_update()
        .get(pk=approval.pk)
    )

    # 🚨 Prevent double decision
    if approval.status in ("APPROVED", "REJECTED"):
        raise ValidationError("Approval already decided")

    approval.status = "APPROVED"
    approval.approved_by = approver
    approval.remarks = remarks
    approval.decided_at = now()
    approval.save(update_fields=[
        "status",
        "approved_by",
        "remarks",
        "decided_at",
    ])

    AuditLog.objects.create(
        actor=approver,
        action="APPROVAL_GRANTED",
        object_type=approval.object_type,
        object_id=approval.object_id,
    )


@transaction.atomic
def reject(approval: Approval, approver, remarks):
    """
    Reject safely with row-level locking and state validation.
    """

    approval = (
        Approval.objects
        .select_for_update()
        .get(pk=approval.pk)
    )

    if approval.status in ("APPROVED", "REJECTED"):
        raise ValidationError("Approval already decided")

    approval.status = "REJECTED"
    approval.approved_by = approver
    approval.remarks = remarks
    approval.decided_at = now()
    approval.save(update_fields=[
        "status",
        "approved_by",
        "remarks",
        "decided_at",
    ])

    AuditLog.objects.create(
        actor=approver,
        action="APPROVAL_REJECTED",
        object_type=approval.object_type,
        object_id=approval.object_id,
    )