import uuid
from django.db import models
from django.conf import settings
from django.utils import timezone
from submissions.models import Submission
from core.identity.models import Role

User = settings.AUTH_USER_MODEL


class CAPA(models.Model):

    STATUS_CHOICES = [
        ("OPEN", "Open"),
        ("ASSIGNED", "Assigned"),
        ("ACTION_DONE", "Action Done"),
        ("REJECTED", "Rejected"),
        ("CLOSED", "Closed"),
    ]

    capa_id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    # ================= RELATIONS =================

    submission = models.ForeignKey(
        Submission,
        on_delete=models.PROTECT,
        related_name="capas",
    )

    # ================= BASIC =================

    title = models.CharField(max_length=255)
    description = models.TextField()
    severity = models.IntegerField()

    # ================= RCA =================

    rca_role = models.ForeignKey(
        Role,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="rca_capas"
    )

    rca_summary = models.TextField(blank=True, null=True)

    rca_submitted_by = models.ForeignKey(
        User,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="rca_submissions"
    )

    rca_submitted_at = models.DateTimeField(null=True, blank=True)

    # ================= CAPA ACTION =================

    capa_role = models.ForeignKey(
        Role,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="capa_action_capas"
    )

    capa_plan = models.TextField(blank=True, null=True)

    capa_submitted_by = models.ForeignKey(
        User,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="capa_submissions"
    )

    capa_submitted_at = models.DateTimeField(null=True, blank=True)

    # ================= ASSIGNMENT =================

    assigned_by = models.ForeignKey(
        User,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="assigned_capas_by_user"
    )

    # ================= WORKFLOW =================

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="OPEN",
    )

    due_date = models.DateField()

    # ================= REJECTION =================

    rejection_reason = models.TextField(blank=True, null=True)

    rejected_by = models.ForeignKey(
        User,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="rejected_capas"
    )

    rejected_at = models.DateTimeField(null=True, blank=True)

    # ================= CLOSURE =================

    closed_at = models.DateTimeField(null=True, blank=True)

    # ================= TIMESTAMP =================

    created_at = models.DateTimeField(auto_now_add=True)

    # ======================================================
    # 🧠 SMART PROPERTIES
    # ======================================================

    @property
    def rca_submitted(self):
        return bool(self.rca_summary and self.rca_summary.strip())

    @property
    def capa_submitted(self):
        return bool(self.capa_plan and self.capa_plan.strip())

    @property
    def is_overdue(self):
        if self.status != "CLOSED" and self.due_date:
            return self.due_date < timezone.now().date()
        return False

    @property
    def is_assignable(self):
        return self.status == "OPEN"

    @property
    def is_ready_for_review(self):
        return self.rca_submitted and self.capa_submitted

    # ======================================================
    # 🔄 WORKFLOW HELPERS
    # ======================================================

    def mark_action_done(self):
        if self.is_ready_for_review:
            self.status = "ACTION_DONE"
            self.save(update_fields=["status"])

    def reject(self, user, reason):
        self.status = "REJECTED"
        self.rejection_reason = reason
        self.rejected_by = user
        self.rejected_at = timezone.now()
        self.save()

    def close(self):
        self.status = "CLOSED"
        self.closed_at = timezone.now()
        self.save(update_fields=["status", "closed_at"])

    # ======================================================

    class Meta:
        indexes = [
            models.Index(fields=["status"]),
            models.Index(fields=["severity"]),
            models.Index(fields=["created_at"]),
            models.Index(fields=["due_date"]),
        ]
        ordering = ["-created_at"]

    def __str__(self):
        return f"CAPA {self.capa_id} - {self.title}"
