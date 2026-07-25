import uuid
from django.db import models
from django.core.exceptions import ValidationError

from org.models import Plant, Product, Department, Shop
from core.identity.models import Role


# =========================================================
# DYNAMIC FORM TEMPLATE (METADATA ONLY)
# =========================================================
class DynamicFormTemplate(models.Model):
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    SUBMISSION_MODE_CHOICES = (
        ("AGGREGATED", "One row per submission"),
        ("FULL", "One row per field"),
    )

    submission_mode = models.CharField(
        max_length=20,
        choices=SUBMISSION_MODE_CHOICES,
        default="AGGREGATED",
        db_index=True,
    )

    code = models.CharField(max_length=50, unique=True)
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)

    is_active = models.BooleanField(default=True, db_index=True)
    is_archived = models.BooleanField(default=False, db_index=True)

    plants = models.ManyToManyField(Plant, blank=True)
    department = models.ForeignKey(
        Department,
        on_delete=models.PROTECT,
        related_name="dynamic_form_templates",
    )
    products = models.ManyToManyField(Product, blank=True)
    shops = models.ManyToManyField(Shop, blank=True)

    # =========================================================
    # APPROVAL CONFIGURATION (NEW SYSTEM)
    # =========================================================
    # Approval flow is defined via TemplateApprovalStep rows
    # No hardcoded enums here

    source_bitable_app_token = models.CharField(max_length=255)
    source_bitable_table_id = models.CharField(max_length=255)
    submission_bitable_app_token = models.CharField(max_length=255)
    submission_bitable_table_id = models.CharField(max_length=255)

    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        indexes = [
            models.Index(fields=["is_active", "is_archived"]),
        ]

    def clean(self):
        super().clean()
        if not self.pk:
            return

        plants = list(self.plants.all())
        if plants:
            invalid_shops = self.shops.exclude(
                plant_id__in=[p.id for p in plants]
            )
            if invalid_shops.exists():
                raise ValidationError(
                    {"shops": "Selected shop does not belong to selected plant(s)."}
                )

    def __str__(self):
        return f"{self.code} - {self.name}"
    
    
class TemplateApprovalStep(models.Model):
    template = models.ForeignKey(
        DynamicFormTemplate,
        on_delete=models.CASCADE,
        related_name="approval_steps",
    )

    category = models.ForeignKey(
        "identity.ApprovalCategory",
        on_delete=models.PROTECT,
    )

    order = models.PositiveIntegerField(
        help_text="Approval order for this template"
    )

    is_required = models.BooleanField(default=True)

    class Meta:
        unique_together = ("template", "category")
        ordering = ["order"]

    def __str__(self):
        return f"{self.template.code} → {self.category.code} ({self.order})"


# =========================================================
# TEMPLATE VERSIONING
# =========================================================
class DynamicFormVersion(models.Model):
    template = models.ForeignKey(
        DynamicFormTemplate,
        on_delete=models.CASCADE,
        related_name="versions"
    )

    version_number = models.PositiveIntegerField()
    is_active = models.BooleanField(default=False)
    is_published = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("template", "version_number")
        ordering = ["-version_number"]

    def __str__(self):
        return f"{self.template.code} v{self.version_number}"


# =========================================================
# FORM FIELD DEFINITION (CORE BUILDER MODEL)
# =========================================================
class DynamicFormField(models.Model):
    """
    One row = ONE FORM FIELD (designed in builder)
    """

    FIELD_KIND_CHOICES = [
        ("INPUT", "Input Field"),
        ("SUPPORT", "Supporting / Reference Data"),
    ]

    DATA_TYPE_CHOICES = [
        ("TEXT", "Text"),
        ("NUMBER", "Number"),
        ("DROPDOWN", "Dropdown"),
        ("BOOLEAN", "Yes / No"),
        ("IMAGE", "Image"),
    ]

    version = models.ForeignKey(
        DynamicFormVersion,
        on_delete=models.CASCADE,
        related_name="fields"
    )

    # -------------------------
    # BASIC FIELD INFO
    # -------------------------
    label = models.CharField(max_length=255)
    help_text = models.CharField(max_length=255, blank=True)

    field_kind = models.CharField(
        max_length=20,
        choices=FIELD_KIND_CHOICES
    )

    data_type = models.CharField(
        max_length=20,
        choices=DATA_TYPE_CHOICES
    )

    required = models.BooleanField(default=False)
    order = models.PositiveIntegerField(default=0)

    # -------------------------
    # BITABLE DATA SOURCE
    # -------------------------
    bitable_column_id = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        help_text="Bitable column used to populate this field"
    )

    # -------------------------
    # FIELD-TO-FIELD DEPENDENCY (🔑 NEW)
    # -------------------------
    depends_on_field = models.ForeignKey(
        "self",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="dependent_fields",
        help_text="Another dropdown field this field depends on"
    )

    # -------------------------
    # CONFIGURATION BLOBS
    # -------------------------

    dropdown_config = models.JSONField(
        default=dict,
        blank=True,
        help_text="""
        {
          "source": "bitable" | "manual",
          "label_column": "<bitable_column_id>",
          "value_column": "<bitable_column_id>",
          "options": ["OK", "NG"]   // only if source = manual
        }
        """
    )

    number_config = models.JSONField(
        default=dict,
        blank=True,
        help_text="""
        {
          "min": { "type": "static" | "column", "value": 220 | "<col_id>" },
          "max": { "type": "static" | "column", "value": 240 | "<col_id>" }
        }
        """
    )

    dependency_config = models.JSONField(
        default=dict,
        blank=True,
        help_text="""
        {
          "operator": "EQ" | "IN",
          "parent_column": "<bitable_column_id>",
          "self_column": "<bitable_column_id>"
        }
        """
    )

    reference_config = models.JSONField(
        default=dict,
        blank=True,
        help_text="""
        {
          "enabled": true,
          "source": "field" | "bitable"
        }
        """
    )

    class Meta:
        ordering = ["order"]
        indexes = [
            models.Index(fields=["version"]),
            models.Index(fields=["data_type"]),
        ]

    def __str__(self):
        return f"{self.label} ({self.data_type})"

# =========================================================
# ROLE → TEMPLATE ASSIGNMENT
# =========================================================
class DynamicTemplateRole(models.Model):
    template = models.ForeignKey(
        DynamicFormTemplate,
        on_delete=models.CASCADE,
        related_name="role_assignments"
    )

    role = models.ForeignKey(
        Role,
        on_delete=models.PROTECT,
        related_name="dynamic_template_assignments"
    )

    # 🔑 THIS IS THE SWITCH
    requires_work_context = models.BooleanField(
        default=False,
        help_text="If enabled, user must have an active Work Context to submit this template"
    )

    class Meta:
        unique_together = ("template", "role")

    def __str__(self):
        return f"{self.template.code} → {self.role.code}"
    
    
# =========================================================
# STANDARD VALUE / COMPARISON RULE
# =========================================================
class DynamicFormStandardRule(models.Model):
    """
    Defines a standard/reference value and comparison logic
    for a target field
    """

    VALUE_SOURCE_CHOICES = (
        ("MANUAL", "Manual Value"),
        ("BITABLE", "Bitable Column"),
    )

    OPERATOR_CHOICES = (
        ("EQ", "Equal"),
        ("LTE", "Less Than or Equal"),
        ("GTE", "Greater Than or Equal"),
    )

    version = models.ForeignKey(
        DynamicFormVersion,
        on_delete=models.CASCADE,
        related_name="standard_rules"
    )

    # 🔗 Which field this rule applies to
    target_field = models.ForeignKey(
        DynamicFormField,
        on_delete=models.CASCADE,
        related_name="standard_rules"
    )

    # -------------------------
    # STANDARD VALUE SOURCE
    # -------------------------
    value_source = models.CharField(
        max_length=20,
        choices=VALUE_SOURCE_CHOICES
    )

    # If MANUAL
    manual_value = models.CharField(
        max_length=255,
        blank=True,
        null=True
    )

    # If BITABLE
    bitable_column_id = models.CharField(
        max_length=255,
        blank=True,
        null=True
    )

    # -------------------------
    # COMPARISON
    # -------------------------
    operator = models.CharField(
        max_length=10,
        choices=OPERATOR_CHOICES
    )

    # -------------------------
    # DEPENDENCY FILTER CONFIG
    # -------------------------
    dependency_filters = models.JSONField(
        default=list,
        blank=True,
        help_text="""
        [
          {
            "field_id": "<DynamicFormField.id>",
            "bitable_column": "<column_id>"
          }
        ]
        """
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=["version"]),
            models.Index(fields=["target_field"]),
        ]

    def __str__(self):
        return f"Rule for {self.target_field.label}"