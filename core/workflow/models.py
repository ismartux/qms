import uuid
from django.db import models
from django.contrib.auth import get_user_model

User = get_user_model()


class Approval(models.Model):
    approval_id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    object_type = models.CharField(
        max_length=50,
        db_index=True,
        help_text="Model name of the approved object (e.g., Submission)"
    )

    object_id = models.CharField(
        max_length=100,
        db_index=True,
        help_text="Primary key of the approved object"
    )

    requested_by = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name="approvals_requested",
        db_index=True,
    )

    approved_by = models.ForeignKey(
        User,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="approvals_completed",
        db_index=True,
    )

    status = models.CharField(
        max_length=20,
        choices=[
            ("PENDING", "Pending"),
            ("APPROVED", "Approved"),
            ("REJECTED", "Rejected"),
        ],
        default="PENDING",
        db_index=True,
    )

    remarks = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    decided_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["object_type", "object_id"]),
            models.Index(fields=["status", "created_at"]),
        ]

    def __str__(self):
        return f"{self.object_type} - {self.object_id} [{self.status}]"