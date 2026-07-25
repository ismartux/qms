import os
import uuid
from django.db import models
from django.conf import settings
from django.utils.text import slugify
from django.contrib.auth import get_user_model
from django.db.models import Q
from PIL import Image
from django.db.models import Index
from org.models import Plant, Shop, Line, Station, Product
from forms_engine.models import ChecklistVersion, ChecklistItem
from core.workflow.states import WorkflowState
from core.utils.image_utils import compress_uploaded_image
from dynamic_forms.models import DynamicFormVersion, DynamicFormField
from core.identity.models import ApprovalCategory

# 🔥 ADD THIS (for middleware-based isolation)
from core.tenant.managers import PlantAwareManager

User = get_user_model()


# =========================================================
# WORK CONTEXT
# =========================================================

class WorkContext(models.Model):

    objects = PlantAwareManager()  # ✅ tenant isolation

    PROCESS_CHOICES = [
        ("IPQC", "IPQC"),
        ("OQC", "OQC"),
        ("FQC", "FQC"),
        ("IQC", "IQC"),
        ("GENERIC", "GENERIC"),
    ]

    SHIFT_CHOICES = [
        ("DAY", "Day"),
        ("NIGHT", "Night"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="active_work_contexts"
    )

    plant = models.ForeignKey(Plant, on_delete=models.PROTECT, db_index=True, null=True, blank=True,)
    shop = models.ForeignKey(Shop, on_delete=models.PROTECT, null=True, blank=True)
    line = models.ForeignKey(Line, on_delete=models.PROTECT, db_index=True)
    product = models.ForeignKey(Product, on_delete=models.PROTECT, db_index=True)

    model_color = models.CharField(max_length=50, blank=True)

    shift = models.CharField(max_length=10, choices=SHIFT_CHOICES)
    work_date = models.DateField(db_index=True)

    process_type = models.CharField(
        max_length=20,
        choices=PROCESS_CHOICES,
        default="GENERIC",
    )

    created_by = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name="created_work_contexts"
    )

    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    is_active = models.BooleanField(default=False, db_index=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["user", "is_active"]),
            models.Index(fields=["plant", "work_date"]),
        ]

    # 🔐 Extra plant consistency safeguard
    def clean(self):
        if self.shop and self.shop.plant_id != self.plant_id:
            raise ValueError("Shop does not belong to selected plant")

        if self.line and self.line.shop.plant_id != self.plant_id:
            raise ValueError("Line does not belong to selected plant")

    def __str__(self):
        return f"{self.plant} | {self.line} | {self.product} | {self.shift} | {self.work_date}"


# =========================================================
# SUBMISSION
# =========================================================

class Submission(models.Model):

    objects = PlantAwareManager()  # ✅ tenant isolation

    submission_id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    work_context = models.ForeignKey(
        WorkContext,
        on_delete=models.PROTECT,
        related_name="submissions",
        null=True,
        blank=True,
    )

    template_version = models.ForeignKey(
        ChecklistVersion,
        on_delete=models.PROTECT,
        related_name="submissions",
        db_index=True,
    )

    plant = models.ForeignKey(Plant, on_delete=models.PROTECT, db_index=True, null=True, blank=True)
    shop = models.ForeignKey(Shop, on_delete=models.PROTECT, null=True, blank=True)
    line = models.ForeignKey(Line, on_delete=models.PROTECT, db_index=True)
    station = models.ForeignKey(Station, on_delete=models.PROTECT, null=True, blank=True)
    product = models.ForeignKey(Product, on_delete=models.PROTECT, db_index=True)

    workflow_state = models.CharField(
        max_length=20,
        choices=WorkflowState.CHOICES,
        default=WorkflowState.DRAFT,
        db_index=True,
    )

    severity_score = models.IntegerField(default=0, db_index=True)

    submitted_by = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name="submissions",
        db_index=True,
    )

    public_approval_token = models.UUIDField(
        default=uuid.uuid4,
        editable=False,
        unique=True,
        db_index=True,
    )

    submitted_at = models.DateTimeField(null=True, blank=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["workflow_state", "plant"]),
            models.Index(fields=["plant", "line", "product"]),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["submitted_by", "template_version", "work_context"],
                condition=Q(workflow_state=WorkflowState.DRAFT),
                name="unique_draft_per_user_template_context"
            )
        ]

    # 🔐 Extra integrity protection
    def clean(self):
        if self.work_context and self.work_context.plant_id != self.plant_id:
            raise ValueError("Submission plant mismatch with work context")

    def is_editable(self):
        return self.workflow_state == WorkflowState.DRAFT

    def __str__(self):
        return str(self.submission_id)


# =========================================================
# SUBMISSION RESPONSES
# =========================================================

class SubmissionResponse(models.Model):
    submission = models.ForeignKey(
        Submission,
        on_delete=models.CASCADE,
        related_name="responses",
    )

    item_id = models.CharField(max_length=100, null=True, blank=True,)
    value = models.TextField(blank=True)
    remark = models.TextField(blank=True, default="")
    is_non_conformance = models.BooleanField(default=False, db_index=True)

    class Meta:
        unique_together = ("submission", "item_id")
        indexes = [
            models.Index(fields=["submission", "item_id"]),
            models.Index(fields=["submission", "is_non_conformance"]),  # 🔥 improved
        ]

    def __str__(self):
        return f"{self.submission.submission_id} - {self.item_id}"


# =========================================================
# ATTACHMENTS
# =========================================================

def evidence_upload_path(instance, filename):
    template = instance.checklist_item.section.version.template
    safe_template_name = slugify(template.name)

    ext = filename.split('.')[-1]
    new_filename = f"{uuid.uuid4()}.{ext}"

    return os.path.join(
        "evidence",
        safe_template_name,
        new_filename
    )


class SubmissionAttachment(models.Model):

    submission = models.ForeignKey(
        Submission,
        related_name="attachments",
        on_delete=models.CASCADE
    )

    checklist_item = models.ForeignKey(
        ChecklistItem,
        on_delete=models.CASCADE
    )

    attachment_type = models.CharField(
        max_length=10,
        choices=[("BASE", "Base"), ("RULE", "Rule")],
        default="BASE",
    )

    file = models.FileField(
        upload_to=evidence_upload_path,
        blank=True,
        null=True
    )

    uploaded_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        unique_together = ("submission", "checklist_item", "attachment_type")
        indexes = [
            models.Index(fields=["submission"]),
        ]

    def save(self, *args, **kwargs):
        if self.file:
            try:
                img = Image.open(self.file)
                img.verify()
                self.file.seek(0)  # 🔥 critical fix for PIL verify
                compressed = compress_uploaded_image(self.file)
                self.file.save(self.file.name, compressed, save=False)
            except Exception:
                pass
        super().save(*args, **kwargs)


# =========================================================
# SYNC LOG
# =========================================================

class SubmissionSyncLog(models.Model):
    submission = models.ForeignKey(
        Submission,
        on_delete=models.CASCADE,
        related_name="sync_logs",
    )
    target = models.CharField(max_length=50)
    status = models.CharField(
        max_length=20,
        choices=[
            ("PENDING", "Pending"),
            ("IN_PROGRESS", "In Progress"),
            ("SUCCESS", "Success"),
            ("FAILED", "Failed"),
        ],
        default="PENDING",
        db_index=True,
    )
    cursor = models.PositiveIntegerField(default=0)
    attempts = models.PositiveIntegerField(default=0)
    error = models.TextField(blank=True)
    last_attempt_at = models.DateTimeField(auto_now=True, db_index=True)

    class Meta:
        unique_together = ("submission", "target")
        indexes = [
            models.Index(fields=["target", "status"]),
        ]

class SubmissionImage(models.Model):
    """Store uploaded evidence images directly in the DB (binary)."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    submission = models.ForeignKey(
        Submission, on_delete=models.CASCADE, related_name="db_images"
    )
    checklist_item = models.ForeignKey(
        ChecklistItem,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
    )
    attachment_type = models.CharField(
        max_length=10,
        choices=[("BASE", "Base"), ("RULE", "Rule")],
        default="BASE",
    )
    image = models.BinaryField()
    content_type = models.CharField(max_length=100, default="image/jpeg")
    filename = models.CharField(max_length=255, blank=True)
    uploaded_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        indexes = [
            models.Index(fields=["submission"]),
        ]

    def __str__(self):
        return f"Image {self.id} for {self.submission_id}"


# =========================================================
# APPROVALS
# =========================================================

class SubmissionApproval(models.Model):
    submission = models.ForeignKey(
        Submission,
        on_delete=models.CASCADE,
        related_name="approvals",
    )

    # 🔑 NEW — approval category (PD / PE / PQE / etc)
    category = models.ForeignKey(
        ApprovalCategory,
        on_delete=models.PROTECT,
        related_name="submission_approvals",
        null=True,
        blank=True,
    )

    approver_role = models.ForeignKey(
        "identity.Role",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
    )

    status = models.CharField(
        max_length=20,
        choices=[
            ("APPROVED", "Approved"),
            ("REJECTED", "Rejected"),
        ],
    )

    approver_name = models.CharField(max_length=100)
    rejection_reason = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)

    # 🚨 NOTHING HERE
    class Meta:
        pass
        
        
        
class ChecklistResponse(models.Model):

    RESPONSE_VALUES = [
        ("YES", "Yes"),
        ("NO", "No"),
        ("NA", "Not Applicable"),
    ]

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False
    )

    # 🔴 CRITICAL FIX
    # Response must belong to a submission
    submission = models.ForeignKey(
        "submissions.Submission",
        on_delete=models.CASCADE,
        related_name="checklist_responses",
        db_index=True,
    )

    item = models.ForeignKey(
        ChecklistItem,
        on_delete=models.CASCADE,
        related_name="responses",
        db_index=True,
    )

    value = models.CharField(
        max_length=3,
        choices=RESPONSE_VALUES,
    )

    remark = models.TextField(blank=True)

    photo = models.ImageField(
        upload_to=evidence_upload_path,
        blank=True,
        null=True,
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
        db_index=True
    )

    # ✅ SAFE IMAGE COMPRESSION
    def save(self, *args, **kwargs):
        is_new = self._state.adding

        if is_new and self.photo:
            compressed = compress_uploaded_image(self.photo)
            self.photo.save(self.photo.name, compressed, save=False)

        super().save(*args, **kwargs)

    class Meta:
        # 🔥 CORRECT UNIQUENESS
        unique_together = ("submission", "item")

        indexes = [
            Index(fields=["submission", "item"]),
            Index(fields=["created_at"]),
        ]

    def is_non_conforming(self):
        return self.value == "NO"

    def __str__(self):
        return f"{self.submission.submission_id} | {self.item.label} → {self.value}"
    
    
class DynamicFormSubmission(models.Model):

    submission_id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    template_version = models.ForeignKey(
        DynamicFormVersion,
        on_delete=models.PROTECT,
        related_name="submissions",
        db_index=True,
    )

    work_context = models.ForeignKey(
        WorkContext,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="dynamic_form_submissions",
    )

    submitted_by = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name="dynamic_form_submissions",
        db_index=True,
    )

    workflow_state = models.CharField(
        max_length=20,
        choices=WorkflowState.CHOICES,
        default=WorkflowState.DRAFT,
        db_index=True,
    )

    # 🔑 ADD THESE
    public_approval_token = models.CharField(
        max_length=64,
        unique=True,
        null=True,
        blank=True,
        db_index=True,
    )

    submitted_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
        
class DynamicFormSubmissionValue(models.Model):

    submission = models.ForeignKey(
        DynamicFormSubmission,
        on_delete=models.CASCADE,
        related_name="values",
    )

    field = models.ForeignKey(
        DynamicFormField,
        on_delete=models.PROTECT,
        related_name="submission_values",
    )

    value = models.TextField(blank=True)
    remark = models.TextField(blank=True, default="")
    is_non_conformance = models.BooleanField(default=False)

    class Meta:
        unique_together = ("submission", "field")
        indexes = [
            models.Index(fields=["submission", "field"]),
        ]
        
class DynamicSubmissionSyncLog(models.Model):

    submission = models.ForeignKey(
        "submissions.DynamicFormSubmission",
        on_delete=models.CASCADE,
        related_name="sync_logs",
    )

    target = models.CharField(max_length=50)

    status = models.CharField(
        max_length=20,
        choices=[
            ("PENDING", "Pending"),
            ("IN_PROGRESS", "In Progress"),
            ("SUCCESS", "Success"),
            ("FAILED", "Failed"),
        ],
        default="PENDING",
        db_index=True,
    )

    attempts = models.PositiveIntegerField(default=0)
    error = models.TextField(blank=True)

    # 🔥 NEW – critical for debugging
    request_payload = models.JSONField(null=True, blank=True)
    response_payload = models.JSONField(null=True, blank=True)
    http_status = models.PositiveIntegerField(null=True, blank=True)

    last_attempt_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("submission", "target")
        
        
class DynamicSubmissionApproval(models.Model):
    submission = models.ForeignKey(
        DynamicFormSubmission,
        on_delete=models.CASCADE,
        related_name="approvals",
    )

    # 🔑 WHAT approval step is being satisfied
    category = models.ForeignKey(
        "identity.ApprovalCategory",
        on_delete=models.PROTECT,
        related_name="dynamic_approvals",
        blank=True,
        null=True,
    )

    # 🔑 WHO approved (role-level audit)
    approver_role = models.ForeignKey(
        "identity.Role",
        on_delete=models.PROTECT,
        related_name="dynamic_approvals",
        blank=True,
        null=True,
    )

    status = models.CharField(
        max_length=20,
        choices=[
            ("APPROVED", "Approved"),
            ("REJECTED", "Rejected"),
        ],
    )

    approver_name = models.CharField(max_length=100)

    rejection_reason = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        # 🔐 Only one approval per category per submission
        unique_together = ("submission", "category")
        ordering = ["created_at"]

    def __str__(self):
        return (
            f"{self.submission_id} | "
            f"{self.category.code} | "
            f"{self.status}"
        )