import os
import uuid
from django.db import models, transaction
from django.core.exceptions import ValidationError
from django.contrib.auth import get_user_model

from org.models import Plant, Department
from core.identity.models import Role
from core.utils.image_utils import compress_uploaded_image

User = get_user_model()


from django.utils.text import slugify

def evidence_upload_path(instance, filename):
    template_name = instance.item.section.version.template.name
    safe_template_name = slugify(template_name)

    ext = filename.split('.')[-1]
    new_filename = f"{uuid.uuid4()}.{ext}"

    return os.path.join(
        "ehs_evidence",
        safe_template_name,
        new_filename
    )

# =========================================================
# ABSTRACT BASE
# =========================================================

class TimeStampedModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


# =========================================================
# EHS FORM BUILDER
# =========================================================

class EHSFormTemplate(TimeStampedModel):

    # =========================================================
    # TEMPLATE TYPE
    # =========================================================

    DAILY = "DAILY"
    SPECIAL = "SPECIAL"

    TEMPLATE_TYPE_CHOICES = [
        (DAILY, "Daily Audit"),
        (SPECIAL, "Special Audit"),
    ]

    # =========================================================
    # RECURRENCE SCOPE (FOR DAILY)
    # =========================================================

    PER_SHIFT = "PER_SHIFT"
    PER_DAY = "PER_DAY"
    PER_WEEK = "PER_WEEK"

    RECURRENCE_SCOPE_CHOICES = [
        (PER_SHIFT, "Per Shift"),
        (PER_DAY, "Per Day"),
        (PER_WEEK, "Per Week"),
    ]

    # =========================================================
    # BASIC INFO
    # =========================================================

    code = models.CharField(max_length=50, unique=True)
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)

    plants = models.ManyToManyField(Plant, blank=True)

    department = models.ForeignKey(
        Department,
        on_delete=models.PROTECT,
        related_name="ehs_form_templates"
    )

    # =========================================================
    # TEMPLATE CONFIGURATION
    # =========================================================

    template_type = models.CharField(
        max_length=20,
        choices=TEMPLATE_TYPE_CHOICES,
        default=DAILY
    )

    # 🔥 Flexible recurrence scope
    recurrence_scope = models.CharField(
        max_length=20,
        choices=RECURRENCE_SCOPE_CHOICES,
        blank=True,
        null=True
    )

    # 🔥 How many times allowed in that scope
    allowed_submissions = models.PositiveIntegerField(
        default=1,
        help_text="Number of submissions allowed per recurrence period"
    )

    # =========================================================
    # SPECIAL AUDIT SETTINGS
    # =========================================================

    require_approval = models.BooleanField(default=False)
    allow_multiple_submissions_per_day = models.BooleanField(default=True)
    require_incident_reference = models.BooleanField(default=False)

    # =========================================================
    # BITABLE
    # =========================================================

    bitable_app_token = models.CharField(
        max_length=255,
        null=True,
        blank=True,
    )

    bitable_table_id = models.CharField(
        max_length=255,
        null=True,
        blank=True,
    )

    # =========================================================
    # STATUS
    # =========================================================

    is_active = models.BooleanField(default=True)
    is_archived = models.BooleanField(default=False)

    # =========================================================
    # VALIDATION
    # =========================================================

    def clean(self):

        # Bitable validation
        if not self.bitable_app_token:
            raise ValidationError({"bitable_app_token": "Required"})

        if not self.bitable_table_id:
            raise ValidationError({"bitable_table_id": "Required"})

        # -------------------------
        # DAILY VALIDATION
        # -------------------------
        if self.template_type == self.DAILY:

            if not self.recurrence_scope:
                raise ValidationError({
                    "recurrence_scope": "Recurrence scope required for Daily templates"
                })

            if self.allowed_submissions < 1:
                raise ValidationError({
                    "allowed_submissions": "Must allow at least 1 submission"
                })

        # -------------------------
        # SPECIAL VALIDATION
        # -------------------------
        if self.template_type == self.SPECIAL:
            # Special audits do not use recurrence logic
            self.recurrence_scope = None
            self.allowed_submissions = 1

    # =========================================================
    # SAVE
    # =========================================================

    def save(self, *args, **kwargs):
        try:
            self.department = Department.objects.get(code="EHS")
        except Department.DoesNotExist:
            raise ValidationError("Department 'EHS' not found")

        self.full_clean()
        super().save(*args, **kwargs)

    # =========================================================
    # STRING
    # =========================================================

    def __str__(self):
        return f"{self.code} - {self.name} ({self.template_type})"

# =========================================================
# TEMPLATE VERSIONING
# =========================================================

class EHSFormVersion(TimeStampedModel):
    template = models.ForeignKey(
        EHSFormTemplate,
        related_name="versions",
        on_delete=models.CASCADE,
    )

    version_number = models.PositiveIntegerField()

    is_active = models.BooleanField(default=False)
    is_published = models.BooleanField(default=False)

    class Meta:
        unique_together = ("template", "version_number")
        ordering = ["-version_number"]

    def clean(self):
        """
        Prevent multiple active or published versions.
        """
        if self.is_active:
            existing_active = EHSFormVersion.objects.filter(
                template=self.template,
                is_active=True
            ).exclude(pk=self.pk)

            if existing_active.exists():
                raise ValidationError(
                    "Only one version can be active at a time."
                )

        if self.is_published:
            existing_published = EHSFormVersion.objects.filter(
                template=self.template,
                is_published=True
            ).exclude(pk=self.pk)

            if existing_published.exists():
                raise ValidationError(
                    "Only one version can be published at a time."
                )

    def save(self, *args, **kwargs):
        with transaction.atomic():

            # 🔥 If activating → deactivate others
            if self.is_active:
                EHSFormVersion.objects.filter(
                    template=self.template,
                    is_active=True
                ).exclude(pk=self.pk).update(is_active=False)

            # 🔥 If publishing → unpublish others
            if self.is_published:
                EHSFormVersion.objects.filter(
                    template=self.template,
                    is_published=True
                ).exclude(pk=self.pk).update(is_published=False)

            self.full_clean()
            super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.template.code} v{self.version_number}"

# =========================================================
# STRUCTURE
# =========================================================

class EHSSection(models.Model):
    version = models.ForeignKey(
        EHSFormVersion,
        related_name="sections",
        on_delete=models.CASCADE
    )

    title = models.CharField(max_length=255)
    order = models.PositiveIntegerField()

    class Meta:
        ordering = ["order"]

    def __str__(self):
        return self.title


class EHSItem(models.Model):

    ITEM_TYPES = [
        ("BOOLEAN", "Yes / No"),
        ("TEXT", "Text"),
        ("NUMBER", "Number"),
        ("PHOTO", "Photo"),
        ("DROPDOWN", "Dropdown"),
        ("DATE", "Date"),
        ("RISK_MATRIX", "Risk Matrix"),
    ]

    section = models.ForeignKey(
        EHSSection,
        related_name="items",
        on_delete=models.CASCADE
    )

    item_id = models.CharField(max_length=100)
    label = models.CharField(max_length=255)
    item_type = models.CharField(max_length=30, choices=ITEM_TYPES)

    required = models.BooleanField(default=False)
    order = models.PositiveIntegerField()

    require_photo_on_no = models.BooleanField(default=False)
    require_remark_on_no = models.BooleanField(default=False)
    escalate_on_no = models.BooleanField(default=False)

    severity_weight = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["order"]
        unique_together = ("section", "item_id")

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)

        if self.item_type == "BOOLEAN":
            if not self.required:
                self.required = True
                super().save(update_fields=["required"])

            self._sync_rules()

    def _sync_rules(self):
        self.rules.filter(condition_value="NO").delete()

        if self.require_photo_on_no:
            EHSRule.objects.create(
                item=self,
                rule_type="PHOTO_REQUIRED",
                condition_value="NO"
            )

        if self.require_remark_on_no:
            EHSRule.objects.create(
                item=self,
                rule_type="REMARK_REQUIRED",
                condition_value="NO"
            )

        if self.escalate_on_no:
            EHSRule.objects.create(
                item=self,
                rule_type="ESCALATE",
                condition_value="NO"
            )

    def __str__(self):
        return self.label



class EHSItemOption(models.Model):
    item = models.ForeignKey(
        EHSItem,
        related_name="options",
        on_delete=models.CASCADE
    )

    label = models.CharField(max_length=255)
    value = models.CharField(max_length=255)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["order"]

    def __str__(self):
        return self.label


# =========================================================
# RULE MODEL
# =========================================================

class EHSRule(models.Model):

    RULE_TYPES = [
        ("PHOTO_REQUIRED", "Photo Required"),
        ("REMARK_REQUIRED", "Remark Required"),
        ("ESCALATE", "Escalate"),
    ]

    item = models.ForeignKey(
        EHSItem,
        related_name="rules",
        on_delete=models.CASCADE
    )

    rule_type = models.CharField(max_length=50, choices=RULE_TYPES)
    condition_value = models.CharField(max_length=50)

    def clean(self):
        if not self.condition_value:
            raise ValidationError("Condition value required")

        self.condition_value = self.condition_value.strip().upper()

        if self.condition_value not in ("YES", "NO"):
            raise ValidationError(
                {"condition_value": "Only YES or NO allowed"}
            )

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.item.label} → {self.rule_type} ({self.condition_value})"


# =========================================================
# SUBMISSION
# =========================================================

class EHSSubmission(TimeStampedModel):

    STATUS_CHOICES = [
        ("DRAFT", "Draft"),
        ("SUBMITTED", "Submitted"),
        ("UNDER_REVIEW", "Under Review"),
        ("APPROVED", "Approved"),
        ("REJECTED", "Rejected"),
        ("CLOSED", "Closed"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    version = models.ForeignKey(EHSFormVersion, on_delete=models.PROTECT)
    plant = models.ForeignKey(Plant, on_delete=models.PROTECT)
    reported_by = models.ForeignKey(User, on_delete=models.PROTECT)

    # 🔥 NEW — For Special Audits
    incident_reference = models.CharField(
        max_length=255,
        blank=True,
        null=True
    )

    status = models.CharField(
        max_length=50,
        choices=STATUS_CHOICES,
        default="DRAFT"
    )

    risk_score = models.PositiveIntegerField(default=0)
    risk_category = models.CharField(max_length=20, blank=True)

    def clean(self):
        template = self.version.template

        if template.template_type == EHSFormTemplate.SPECIAL:
            if template.require_incident_reference and not self.incident_reference:
                raise ValidationError({
                    "incident_reference": "Incident reference required for this Special Audit"
                })

    def __str__(self):
        return f"{self.version.template.code} - {self.status}"


class EHSResponse(models.Model):

    RESPONSE_VALUES = [
        ("YES", "Yes"),
        ("NO", "No"),
        ("NA", "Not Applicable"),
    ]

    submission = models.ForeignKey(
        EHSSubmission,
        related_name="responses",
        on_delete=models.CASCADE
    )

    item = models.ForeignKey(EHSItem, on_delete=models.CASCADE)

    value = models.CharField(
        max_length=3,
        choices=RESPONSE_VALUES,
        blank=True,
        null=True
    )

    remark = models.TextField(blank=True)

    photo = models.ImageField(
        upload_to=evidence_upload_path,
        blank=True,
        null=True
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("submission", "item")

    def save(self, *args, **kwargs):
        # Lazy import to prevent circular import
        from ehs_engine.services.rule_engine import RuleEngine
        from ehs_engine.services.risk_engine import RiskEngine

        # Validate rules BEFORE saving
        RuleEngine.validate_response(self)

        if self.photo and self._state.adding:
            compressed = compress_uploaded_image(self.photo)
            self.photo.save(self.photo.name, compressed, save=False)

        super().save(*args, **kwargs)

        # Centralized risk processing
        if self.value:
            RiskEngine.process_submission(self.submission)


# =========================================================
# RISK MATRIX
# =========================================================

class RiskAssessment(models.Model):
    submission = models.OneToOneField(
        EHSSubmission,
        related_name="risk_assessment",
        on_delete=models.CASCADE
    )

    likelihood = models.PositiveSmallIntegerField()
    severity = models.PositiveSmallIntegerField()

    @property
    def score(self):
        return self.likelihood * self.severity


# =========================================================
# WORKFLOW
# =========================================================

class EHSWorkflowTemplate(models.Model):
    name = models.CharField(max_length=255)
    template = models.ForeignKey(EHSFormTemplate, on_delete=models.CASCADE)


class WorkflowStep(models.Model):
    workflow = models.ForeignKey(
        EHSWorkflowTemplate,
        related_name="steps",
        on_delete=models.CASCADE
    )
    order = models.PositiveIntegerField()
    role_required = models.ForeignKey(Role, on_delete=models.PROTECT)

    class Meta:
        ordering = ["order"]


class WorkflowActionLog(TimeStampedModel):
    submission = models.ForeignKey(
        EHSSubmission,
        related_name="workflow_logs",
        on_delete=models.CASCADE
    )
    action = models.CharField(max_length=100)
    performed_by = models.ForeignKey(User, on_delete=models.PROTECT)
    comment = models.TextField(blank=True)


# =========================================================
# CAPA
# =========================================================

class CAPA(TimeStampedModel):

    STATUS_CHOICES = [
        ("OPEN", "Open"),
        ("IN_PROGRESS", "In Progress"),
        ("COMPLETED", "Completed"),
        ("VERIFIED", "Verified"),
    ]

    submission = models.ForeignKey(
        EHSSubmission,
        related_name="capas",
        on_delete=models.CASCADE
    )

    corrective_action = models.TextField()
    preventive_action = models.TextField(blank=True)

    responsible_person = models.ForeignKey(User, on_delete=models.PROTECT)

    target_date = models.DateField()

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="OPEN"
    )

    def __str__(self):
        return f"CAPA - {self.submission.id}"
    
    
    
class EHSNotification(models.Model):

    recipient = models.ForeignKey(
        User,
        related_name="ehs_notifications",
        on_delete=models.CASCADE
    )

    title = models.CharField(max_length=255)
    message = models.TextField()

    submission = models.ForeignKey(
        EHSSubmission,
        on_delete=models.CASCADE,
        null=True,
        blank=True
    )

    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.title