# Migration for DCC Permissions
from django.db import migrations


def create_dcc_permissions(apps, schema_editor):
    Permission = apps.get_model('identity', 'Permission')
    Role = apps.get_model('identity', 'Role')
    RolePermission = apps.get_model('identity', 'RolePermission')

    p_access, _ = Permission.objects.get_or_create(
        code='can_access_dcc',
        defaults={
            'name': 'Can Access DCC',
            'description': 'Allows accessing the Document Control Center (DCC)',
            'is_active': True
        }
    )
    p_manage, _ = Permission.objects.get_or_create(
        code='can_manage_dcc',
        defaults={
            'name': 'Can Manage DCC',
            'description': 'Allows managing DCC users, masters, stamps, and templates',
            'is_active': True
        }
    )
    p_approve, _ = Permission.objects.get_or_create(
        code='can_approve_dcc',
        defaults={
            'name': 'Can Approve DCC Documents',
            'description': 'Allows approving documents in the DCC Approval Desk',
            'is_active': True
        }
    )
    p_intake, _ = Permission.objects.get_or_create(
        code='can_intake_dcc',
        defaults={
            'name': 'Can Intake DCC Documents',
            'description': 'Allows performing document intake and stamping (DCC MAM)',
            'is_active': True
        }
    )

    # Automatically grant access to administrative roles if they exist
    for role_code in ['ADMIN', 'EHS_ADMIN', 'QA_ASSY_TL', 'PQE']:
        role = Role.objects.filter(code=role_code).first()
        if role:
            RolePermission.objects.get_or_create(role=role, permission=p_access)
            if role_code in ['ADMIN', 'EHS_ADMIN']:
                RolePermission.objects.get_or_create(role=role, permission=p_manage)


def remove_dcc_permissions(apps, schema_editor):
    Permission = apps.get_model('identity', 'Permission')
    Permission.objects.filter(code__in=[
        'can_access_dcc', 'can_manage_dcc', 'can_approve_dcc', 'can_intake_dcc'
    ]).delete()


class Migration(migrations.Migration):
    dependencies = [
        ('identity', '0017_employeeprofile_dcc_access_and_more'),
    ]

    operations = [
        migrations.RunPython(create_dcc_permissions, remove_dcc_permissions),
    ]

