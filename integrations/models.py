from django.db import models
from django.core.exceptions import ValidationError
from org.models import Plant
from forms_engine.models import ChecklistTemplate


# =====================================================
# INTEGRATION TARGET (Global System)
# =====================================================
class IntegrationTarget(models.Model):
    code = models.CharField(max_length=50, unique=True, db_index=True)
    name = models.CharField(max_length=100)

    is_active = models.BooleanField(default=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


# =====================================================
# TEMPLATE → TARGET MAPPING (Plant Scoped)
# =====================================================
class IntegrationTemplateMapping(models.Model):

    plant = models.ForeignKey(
        Plant,
        on_delete=models.PROTECT,
        related_name="integration_mappings",
        db_index=True,
        null=True,
        blank=True,
    )

    template = models.ForeignKey(
        ChecklistTemplate,
        on_delete=models.CASCADE,
        related_name="integration_mappings",
        db_index=True,
    )

    target = models.ForeignKey(
        IntegrationTarget,
        on_delete=models.CASCADE,
        related_name="template_mappings",
        db_index=True,
    )

    external_table_id = models.CharField(max_length=100)

    enabled = models.BooleanField(default=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("plant", "template", "target")
        indexes = [
            models.Index(fields=["plant", "enabled"]),
            models.Index(fields=["template", "enabled"]),
        ]

    def clean(self):
        # Ensure template is applicable to this plant
        if self.template.plants.exists():
            if not self.template.plants.filter(id=self.plant_id).exists():
                raise ValidationError(
                    {"plant": "Template is not assigned to this plant."}
                )

    def __str__(self):
        return f"{self.plant.name} | {self.template.code} → {self.target.code}"


# =====================================================
# FIELD MAPPING
# =====================================================
class IntegrationFieldMapping(models.Model):

    template_mapping = models.ForeignKey(
        IntegrationTemplateMapping,
        on_delete=models.CASCADE,
        related_name="fields",
        db_index=True,
    )

    item_id = models.CharField(max_length=100)
    external_field = models.CharField(max_length=100)

    transform = models.CharField(
        max_length=50,
        blank=True,
        help_text="Optional transformation logic key"
    )

    class Meta:
        unique_together = ("template_mapping", "item_id")
        indexes = [
            models.Index(fields=["template_mapping"]),
        ]

    def __str__(self):
        return f"{self.item_id} → {self.external_field}"