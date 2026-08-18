# Generated migration for admin panel permission
from django.db import migrations


def create_admin_panel_permission(apps, schema_editor):
    """Create admin panel access permission"""
    Permission = apps.get_model('identity', 'Permission')
    
    Permission.objects.get_or_create(
        code='can_access_admin_panel',
        defaults={
            'name': 'Can Access Admin Panel',
            'description': 'Allows access to the admin panel mode in the sidebar',
            'is_active': True
        }
    )


def remove_admin_panel_permission(apps, schema_editor):
    """Remove admin panel permission"""
    Permission = apps.get_model('identity', 'Permission')
    Permission.objects.filter(code='can_access_admin_panel').delete()


class Migration(migrations.Migration):
    dependencies = [
        ('identity', '0014_forms_engine_permissions'),
    ]

    operations = [
        migrations.RunPython(create_admin_panel_permission, remove_admin_panel_permission),
    ]