from django.db import models
from django.core.exceptions import ValidationError
import pytz


# =========================
# COMPANY
# =========================
class Company(models.Model):
    code = models.CharField(max_length=50, unique=True, db_index=True)
    name = models.CharField(max_length=255)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


# =========================
# PLANT
# =========================
class Plant(models.Model):
    company = models.ForeignKey(
        Company,
        on_delete=models.PROTECT,
        related_name="plants",
        db_index=True,
    )
    code = models.CharField(max_length=50)
    name = models.CharField(max_length=255)
    timezone = models.CharField(max_length=50, default="UTC")
    is_active = models.BooleanField(default=True)

    def clean(self):
        try:
            pytz.timezone(self.timezone)
        except Exception:
            raise ValidationError(
                {"timezone": "Invalid timezone. Use IANA format (e.g. Asia/Kolkata)"}
            )

    class Meta:
        unique_together = ("company", "code")
        ordering = ["name"]

    def __str__(self):
        return f"{self.name} ({self.company.name})"


# =========================
# DEPARTMENT
# =========================
class Department(models.Model):
    plant = models.ForeignKey(
        Plant,
        on_delete=models.PROTECT,
        related_name="departments",
        db_index=True,
        null=True,
        blank=True,
    )
    code = models.CharField(max_length=50)
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        unique_together = ("plant", "code")
        ordering = ["name"]

    def __str__(self):
        if self.plant:
            return f"{self.name} ({self.plant.name})"
        return self.name


# =========================
# SHOP
# =========================
class Shop(models.Model):
    plant = models.ForeignKey(
        Plant,
        on_delete=models.PROTECT,
        related_name="shops",
        db_index=True,
        null=True,
        blank=True,
    )
    code = models.CharField(max_length=50)
    name = models.CharField(max_length=255)
    is_active = models.BooleanField(default=True)

    class Meta:
        unique_together = ("plant", "code")
        ordering = ["name"]

    def __str__(self):
        if self.plant:
            return f"{self.name} - {self.plant.name}"
        return self.name


# =========================
# LINE
# =========================
class Line(models.Model):
    shop = models.ForeignKey(
        Shop,
        on_delete=models.PROTECT,
        related_name="lines",
        db_index=True,
    )
    code = models.CharField(max_length=50)
    name = models.CharField(max_length=255)
    is_active = models.BooleanField(default=True)

    class Meta:
        unique_together = ("shop", "code")
        ordering = ["name"]

    def __str__(self):
        return f"{self.name} ({self.shop.name})"


# =========================
# STATION
# =========================
class Station(models.Model):
    line = models.ForeignKey(
        Line,
        on_delete=models.PROTECT,
        related_name="stations",
        db_index=True,
    )
    code = models.CharField(max_length=50)
    name = models.CharField(max_length=255)
    is_active = models.BooleanField(default=True)

    class Meta:
        unique_together = ("line", "code")
        ordering = ["name"]

    def __str__(self):
        return f"{self.name} ({self.line.name})"


# =========================
# PRODUCT
# =========================
class Product(models.Model):
    company = models.ForeignKey(
        Company,
        on_delete=models.PROTECT,
        related_name="products",
        db_index=True,
    )
    plant = models.ForeignKey(
        Plant,
        on_delete=models.PROTECT,
        related_name="products",
        null=True,
        blank=True,
        db_index=True,
        help_text="Leave empty if product is common across all plants",
    )

    code = models.CharField(max_length=50)
    name = models.CharField(max_length=255)

    category = models.CharField(max_length=100, blank=True)
    position = models.CharField(max_length=100, blank=True)
    brand = models.CharField(max_length=100, blank=True)

    is_active = models.BooleanField(default=True)

    class Meta:
        unique_together = (
            ("company", "code"),
            ("plant", "code"),
        )
        ordering = ["name"]

    def clean(self):
        if self.plant and self.plant.company_id != self.company_id:
            raise ValidationError(
                {"plant": "Selected plant does not belong to the selected company."}
            )

    def __str__(self):
        if self.plant:
            return f"{self.name} ({self.plant.name})"
        return f"{self.name} ({self.company.name})"