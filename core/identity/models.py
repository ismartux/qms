from django.db import models
from django.conf import settings
from django.core.exceptions import ValidationError
from org.models import Plant, Department


# =====================================================
# USER SCOPE (Plant-Level Access Control)
# =====================================================
class UserScope(models.Model):

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="scopes",
        db_index=True,
    )

    plant = models.ForeignKey(
        Plant,
        on_delete=models.PROTECT,
        related_name="user_scopes",
        db_index=True,
    )

    department = models.ForeignKey(
        Department,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        db_index=True,
        help_text="Optional department restriction within plant",
    )

    role = models.ForeignKey(
        "identity.Role",
        on_delete=models.PROTECT,
        related_name="user_scopes",
        db_index=True,
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("user", "plant")
        indexes = [
            models.Index(fields=["user", "plant"]),
            models.Index(fields=["plant", "role"]),
        ]

    def clean(self):
        # Prevent inconsistent plant-department mapping
        if self.department and self.department.plant_id != self.plant_id:
            raise ValidationError(
                {"department": "Department does not belong to selected plant"}
            )

    def __str__(self):
        return f"{self.user.username} - {self.role.name} @ {self.plant.name}"


# =====================================================
# ROLE
# =====================================================
class Role(models.Model):

    code = models.CharField(
        max_length=50,
        unique=True,
        help_text="Internal role code (e.g. QC, SUPERVISOR)",
        db_index=True,
    )

    name = models.CharField(
        max_length=100,
        help_text="Display name (e.g. Quality Control)"
    )
    
    
    approval_categories = models.ManyToManyField(
        "identity.ApprovalCategory",
        blank=True,
        related_name="roles",
        help_text="Approval categories this role can approve"
    )

    is_active = models.BooleanField(default=True, db_index=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]

    def save(self, *args, **kwargs):
        self.code = self.code.strip().upper()
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name


# =====================================================
# EMPLOYEE PROFILE
# =====================================================
class EmployeeProfile(models.Model):

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="employee_profile",
    )

    employee_id = models.CharField(
        max_length=50,
        unique=True,
        db_index=True,
    )
    
    # 🔑 GLOBAL ROLE (FOR STANDALONE FORMS)
    role = models.ForeignKey(
        "identity.Role",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="employee_profiles",
    )

    # 🔐 Plain password storage (superuser-only access)
    plain_password = models.CharField(
        max_length=128,
        blank=True,
        default="",
        help_text="Last-set plain text password — visible to superusers only",
    )

    # 📄 DCC ACCESS & RBAC CONFIGURATION
    dcc_access = models.BooleanField(
        default=False,
        help_text="Grants access to Document Control Center (DCC)"
    )
    dcc_role = models.CharField(
        max_length=30,
        blank=True,
        default="",
        choices=[
            ('USER', 'User / Initiator'),
            ('ENGINEER_SUPERVISOR', 'Engineer / Supervisor'),
            ('SUPERVISOR_AM', 'Supervisor / AM'),
            ('DEPT_AM', 'Dept Assistant Manager (AM)'),
            ('HOD', 'Head of Department (HOD)'),
            ('GM', 'General Manager (GM)'),
            ('QA_SUPERVISOR_AM', 'QA Supervisor / AM'),
            ('QA_MANAGER', 'QA Manager'),
            ('SECTION_HEAD', 'Section Head'),
            ('FACTORY_HEAD', 'Factory Head'),
            ('DCC_MAM', 'DCC Coordinator (Document Control)'),
            ('ADMIN', 'DCC Administrator'),
        ],
        help_text="Assigned Role in DCC Document Control Center"
    )
    dcc_department_code = models.CharField(
        max_length=20,
        blank=True,
        default="",
        help_text="DCC Department Code (PRD, QA, MNT, STR, DCC)"
    )
    dcc_is_hod = models.BooleanField(
        default=False,
        help_text="Designated Head of Department (HOD) in DCC"
    )
    dcc_is_am = models.BooleanField(
        default=False,
        help_text="Designated Assistant Manager (AM) in DCC"
    )

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.employee_id} - {self.user.username}"
    
    
class Permission(models.Model):
    code = models.CharField(
        max_length=100,
        unique=True,
        db_index=True,
        help_text="Internal permission code (snake_case)"
    )
    name = models.CharField(max_length=150)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["code"]

    def save(self, *args, **kwargs):
        self.code = self.code.strip().lower()
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name
    
    
class RolePermission(models.Model):
    role = models.ForeignKey(
        "identity.Role",
        on_delete=models.CASCADE,
        related_name="role_permissions"
    )
    permission = models.ForeignKey(
        Permission,
        on_delete=models.CASCADE,
        related_name="permission_roles"
    )

    class Meta:
        unique_together = ("role", "permission")
        
        
class ApprovalCategory(models.Model):
    """
    Defines an approval step/category (e.g. PD, PE, PQE, SAFETY, QA, etc.)
    """

    code = models.CharField(
        max_length=50,
        unique=True,
        help_text="Short unique code like PD, PE, PQE, SAFETY"
    )

    name = models.CharField(
        max_length=100,
        help_text="Human readable name"
    )

    is_active = models.BooleanField(default=True)

    # 🔑 controls whether this category participates in approval logic
    is_approver = models.BooleanField(
        default=True,
        help_text="Whether this category can be used in approval flows"
    )

    order = models.PositiveIntegerField(
        default=0,
        help_text="Global default order (lower = earlier)"
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["order", "code"]

    def __str__(self):
        return self.code