"""
Management command: setup_scanner_permissions

Creates:
  - Permission: can_access_qr_scanner
  - Role: SCANNER
  - Assigns permission to SCANNER role

Usage:
    python manage.py setup_scanner_permissions
"""

from django.core.management.base import BaseCommand
from core.identity.models import Permission, Role, RolePermission


class Command(BaseCommand):
    help = "Set up QR Scanner permission and SCANNER role"

    def handle(self, *args, **options):
        # 1. Create permission
        perm, perm_created = Permission.objects.get_or_create(
            code="can_access_qr_scanner",
            defaults={
                "name": "Can Access QR Scanner",
                "description": "Allows access to the QR Scan and QR Scan Report pages.",
                "is_active": True,
            },
        )
        if perm_created:
            self.stdout.write(self.style.SUCCESS("  ✅ Created permission: can_access_qr_scanner"))
        else:
            self.stdout.write(self.style.WARNING("  ⚠️  Permission already exists: can_access_qr_scanner"))

        # 2. Create SCANNER role
        role, role_created = Role.objects.get_or_create(
            code="SCANNER",
            defaults={
                "name": "QR Scanner",
                "is_active": True,
            },
        )
        if role_created:
            self.stdout.write(self.style.SUCCESS("  ✅ Created role: SCANNER (QR Scanner)"))
        else:
            self.stdout.write(self.style.WARNING("  ⚠️  Role already exists: SCANNER"))

        # 3. Assign permission to role
        rp, rp_created = RolePermission.objects.get_or_create(
            role=role,
            permission=perm,
        )
        if rp_created:
            self.stdout.write(self.style.SUCCESS("  ✅ Assigned can_access_qr_scanner to SCANNER role"))
        else:
            self.stdout.write(self.style.WARNING("  ⚠️  Permission already assigned to SCANNER role"))

        self.stdout.write(self.style.SUCCESS("\n✅ QR Scanner permissions setup complete!"))
        self.stdout.write(
            "\nTo assign SCANNER role to a user, go to:\n"
            "  Admin Panel → Access Control → User Scopes → assign SCANNER role to a user for a plant."
        )
