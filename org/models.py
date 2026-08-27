from django.db import models
from django.conf import settings
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
# FLOOR
# =========================
class Floor(models.Model):
    plant = models.ForeignKey(
        Plant,
        on_delete=models.PROTECT,
        related_name="floors",
        db_index=True,
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
# LINE
# =========================
class Line(models.Model):
    shop = models.ForeignKey(
        Shop,
        on_delete=models.PROTECT,
        related_name="lines",
        db_index=True,
    )
    floor = models.ForeignKey(
        Floor,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
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


# =========================
# FLOOR-WISE TL ASSIGNMENT
# =========================
class FloorTLAssignment(models.Model):
    SHIFT_CHOICES = [
        ("ALL", "All Shifts"),
        ("DAY", "Day"),
        ("NIGHT", "Night"),
    ]

    floor = models.ForeignKey(
        Floor,
        on_delete=models.CASCADE,
        related_name="tl_assignments",
        db_index=True,
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="floor_tl_assignments",
        db_index=True,
        help_text="Team Leader (TL) user",
    )
    shift = models.CharField(
        max_length=10,
        choices=SHIFT_CHOICES,
        default="ALL",
    )
    is_active = models.BooleanField(default=True, db_index=True)
    assigned_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_floor_tl_assignments",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["floor", "-created_at"]
        indexes = [
            models.Index(fields=["floor", "is_active"]),
            models.Index(fields=["user", "is_active"]),
        ]

    def __str__(self):
        return f"TL: {self.user.get_full_name() or self.user.username} @ {self.floor.name} ({self.shift})"


# =========================
# SHOP-WISE PQE ASSIGNMENT
# =========================
class ShopPQEAssignment(models.Model):
    shop = models.ForeignKey(
        Shop,
        on_delete=models.CASCADE,
        related_name="pqe_assignments",
        db_index=True,
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="shop_pqe_assignments",
        db_index=True,
        help_text="Product Quality Engineer (PQE) user",
    )
    is_active = models.BooleanField(default=True, db_index=True)
    assigned_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_shop_pqe_assignments",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["shop", "-created_at"]
        indexes = [
            models.Index(fields=["shop", "is_active"]),
            models.Index(fields=["user", "is_active"]),
        ]

    def __str__(self):
        return f"PQE: {self.user.get_full_name() or self.user.username} @ {self.shop.name}"


# =========================
# IPQC MAPPING
# =========================
class IPQCMapping(models.Model):
    SHIFT_CHOICES = [
        ("ALL", "All Shifts"),
        ("DAY", "Day"),
        ("NIGHT", "Night"),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="ipqc_mappings",
        db_index=True,
        help_text="IPQC Inspector / Operator",
    )
    plant = models.ForeignKey(
        Plant,
        on_delete=models.PROTECT,
        related_name="ipqc_mappings",
        db_index=True,
    )
    floor = models.ForeignKey(
        Floor,
        on_delete=models.PROTECT,
        related_name="ipqc_mappings",
        db_index=True,
    )
    shop = models.ForeignKey(
        Shop,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="ipqc_mappings",
        db_index=True,
    )
    lines = models.ManyToManyField(
        Line,
        blank=True,
        related_name="ipqc_mappings",
        help_text="Assigned lines for this IPQC (leave empty for all lines in shop/floor)",
    )
    shift = models.CharField(
        max_length=10,
        choices=SHIFT_CHOICES,
        default="ALL",
    )
    is_active = models.BooleanField(default=True, db_index=True)
    assigned_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_ipqc_mappings",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["user", "is_active"]),
            models.Index(fields=["plant", "floor", "shop"]),
        ]

    def get_active_tls(self):
        """Returns QuerySet of active TL assignments for this mapping's floor and shift"""
        if not self.floor:
            return FloorTLAssignment.objects.none()
        qs = FloorTLAssignment.objects.filter(floor=self.floor, is_active=True).select_related("user")
        if self.shift != "ALL":
            qs = qs.filter(shift__in=[self.shift, "ALL"])
        return qs

    def get_active_pqes(self):
        """Returns QuerySet of active PQE assignments for this mapping's shop"""
        if not self.shop:
            return ShopPQEAssignment.objects.none()
        return ShopPQEAssignment.objects.filter(shop=self.shop, is_active=True).select_related("user")

    def __str__(self):
        user_display = self.user.get_full_name() or self.user.username
        shop_name = self.shop.name if self.shop else "No Shop"
        floor_name = self.floor.name if self.floor else "No Floor"
        return f"IPQC Mapping: {user_display} | Floor: {floor_name} | Shop: {shop_name}"