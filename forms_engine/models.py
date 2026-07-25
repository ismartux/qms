import os
import uuid
from django.db import models
from django.core.exceptions import ValidationError

from org.models import Plant, Product, Department, Shop
from core.identity.models import Role


# =========================================================
# CHECKLIST TEMPLATE (FORM DEFINITION)
# =========================================================
class ChecklistTemplate(models.Model):
    APPROVAL_FLOW_CHOICES = [
        ("NONE", "No Approval Required"),
        ("PD", "PD Only"),
        ("PE", "PE Only"),
        ("PQE", "PQE Only"),
        ("PD_PQE", "PD + PQE"),
        ("PE_PQE", "PE + PQE"),
        ("PD_PE_PQE", "PD + PE + PQE (Full Chain)"),
    ]

    code = models.CharField(max_length=50, unique=True)
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)

    is_active = models.BooleanField(default=True, db_index=True)
    is_archived = models.BooleanField(default=False, db_index=True)

    # -------------------------
    # SCOPE / APPLICABILITY
    # -------------------------
    plants = models.ManyToManyField(Plant, blank=True)

    department = models.ForeignKey(
        Department,
        on_delete=models.PROTECT,
        related_name="checklist_templates",
    )

    products = models.ManyToManyField(Product, blank=True)

    shops = models.ManyToManyField(
        Shop,
        blank=True,
        related_name="checklist_templates",
    )

    

    # -------------------------
    # BITABLE INTEGRATION
    # -------------------------
    bitable_app_token = models.CharField(max_length=255, blank=True, null=True)
    bitable_table_id = models.CharField(max_length=255, blank=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        indexes = [
            models.Index(fields=["is_active", "is_archived"]),
            models.Index(fields=["created_at"]),
        ]

    def clean(self):
        super().clean()
        if not self.pk:
            return

        plants = list(self.plants.all())
        if not plants:
            return

        invalid_shops = self.shops.exclude(
            plant_id__in=[p.id for p in plants]
        )
        if invalid_shops.exists():
            raise ValidationError(
                {"shops": "Selected shop does not belong to selected plant(s)."}
            )

    def __str__(self):
        return f"{self.code} - {self.name}"
    
    
class ChecklistApprovalStep(models.Model):
    template = models.ForeignKey(
        ChecklistTemplate,
        on_delete=models.CASCADE,
        related_name="approval_steps",
    )

    category = models.ForeignKey(
        "identity.ApprovalCategory",
        on_delete=models.PROTECT,
        related_name="checklist_steps",
    )

    order = models.PositiveIntegerField(
        help_text="Lower number = earlier approval"
    )

    is_required = models.BooleanField(
        default=True,
        help_text="If false, approval is optional"
    )

    class Meta:
        unique_together = ("template", "category")
        ordering = ["order"]

    def __str__(self):
        return f"{self.template.code} → {self.category.code}"
    


# =========================================================
# TEMPLATE VERSIONING
# =========================================================
class ChecklistVersion(models.Model):
    template = models.ForeignKey(
        ChecklistTemplate,
        related_name="versions",
        on_delete=models.CASCADE,
    )

    version_number = models.PositiveIntegerField()
    is_active = models.BooleanField(default=False, db_index=True)     # Active version
    is_published = models.BooleanField(default=False, db_index=True)  # Locked & usable

    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        unique_together = ("template", "version_number")
        ordering = ["-version_number"]
        indexes = [
            models.Index(fields=["template", "is_active"]),
            models.Index(fields=["template", "is_published"]),
        ]

    def __str__(self):
        return f"{self.template.code} v{self.version_number}"


# =========================================================
# CHECKLIST STRUCTURE
# =========================================================
class ChecklistSection(models.Model):
    version = models.ForeignKey(
        ChecklistVersion,
        on_delete=models.CASCADE,
        related_name="sections",
    )

    title = models.CharField(max_length=255)
    order = models.PositiveIntegerField()

    class Meta:
        ordering = ["order"]
        indexes = [
            models.Index(fields=["version", "order"]),
        ]

    def __str__(self):
        return self.title


class ChecklistItem(models.Model):
    ITEM_TYPES = [
        ("BOOLEAN", "Yes / No"),
        ("TEXT", "Text"),
        ("NUMBER", "Number"),
        ("PHOTO", "Photo"),
        ("DROPDOWN", "Dropdown"),
    ]

    section = models.ForeignKey(
        ChecklistSection,
        on_delete=models.CASCADE,
        related_name="items",
    )

    item_id = models.CharField(
        max_length=100,
        help_text="Stable identifier (used in rules & integrations)"
    )

    label = models.TextField()
    item_type = models.CharField(max_length=20, choices=ITEM_TYPES)
    required = models.BooleanField(default=False)

    order = models.PositiveIntegerField()

    severity_weight = models.PositiveSmallIntegerField(
        default=0,
        help_text="Severity contribution if non-conforming"
    )

    class Meta:
        ordering = ["order"]
        unique_together = ("section", "item_id")
        indexes = [
            models.Index(fields=["section", "order"]),
        ]

    def __str__(self):
        return self.label


class ChecklistItemOption(models.Model):
    item = models.ForeignKey(
        ChecklistItem,
        on_delete=models.CASCADE,
        related_name="options",
    )

    label = models.CharField(max_length=255)
    value = models.CharField(max_length=255)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["order"]
        indexes = [
            models.Index(fields=["item", "order"]),
        ]

    def __str__(self):
        return self.label


# =========================================================
# RULE ENGINE
# =========================================================
class ChecklistRule(models.Model):
    RULE_TYPES = [
        ("PHOTO_REQUIRED", "Photo Required"),
        ("REMARK_REQUIRED", "Remark Required"),
    ]

    item = models.ForeignKey(
        ChecklistItem,
        on_delete=models.CASCADE,
        related_name="rules",
    )

    rule_type = models.CharField(
        max_length=50,
        choices=RULE_TYPES
    )

    condition_value = models.CharField(
        max_length=50,
        help_text="Expected value (YES / NO)"
    )

    def clean(self):
        if self.condition_value:
            self.condition_value = self.condition_value.strip().upper()

            # ✅ NA is allowed in responses, but rules must not depend on NA
            if self.condition_value not in ("YES", "NO"):
                raise ValidationError(
                    {"condition_value": "Rules can only target YES or NO"}
                )

    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)


# =========================================================
# EVIDENCE UPLOAD PATH FUNCTION
# =========================================================
from django.utils.text import slugify

def evidence_upload_path(instance, filename):
    template = (
        instance.item.section.version.template
    )

    safe_template_name = slugify(template.name)

    ext = filename.split('.')[-1]
    new_filename = f"{uuid.uuid4()}.{ext}"

    return os.path.join(
        "evidence",
        safe_template_name,
        str(template.id),
        new_filename
    )

# =========================================================
# ROLE → TEMPLATE MAPPING
# =========================================================
class TemplateRole(models.Model):
    template = models.ForeignKey(
        ChecklistTemplate,
        on_delete=models.CASCADE,
        related_name="role_assignments"
    )

    role = models.ForeignKey(
        Role,
        on_delete=models.PROTECT,
        related_name="template_assignments"
    )

    class Meta:
        unique_together = ("template", "role")

    def __str__(self):
        return f"{self.template.code} → {self.role.code}"
