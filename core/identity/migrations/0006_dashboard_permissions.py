# Generated migration for dashboard permissions
from django.db import migrations


def create_dashboard_permissions(apps, schema_editor):
    """Create dashboard-related permissions"""
    Permission = apps.get_model('identity', 'Permission')
    
    permissions = [
        {
            'code': 'can_view_operator_dashboard',
            'name': 'Can View Operator Dashboard',
            'description': 'Allows access to operator-level dashboard with personal metrics and scheduled forms'
        },
        {
            'code': 'can_view_supervisor_dashboard',
            'name': 'Can View Supervisor Dashboard',
            'description': 'Allows access to supervisor dashboard with team overview and performance metrics'
        },
        {
            'code': 'can_view_management_dashboard',
            'name': 'Can View Management Dashboard',
            'description': 'Allows access to management dashboard with plant-wide analytics and trends'
        },
    ]
    
    for perm_data in permissions:
        Permission.objects.get_or_create(
            code=perm_data['code'],
            defaults={
                'name': perm_data['name'],
                'description': perm_data['description'],
                'is_active': True
            }
        )


def remove_dashboard_permissions(apps, schema_editor):
    """Remove dashboard permissions"""
    Permission = apps.get_model('identity', 'Permission')
    Permission.objects.filter(
        code__in=[
            'can_view_operator_dashboard',
            'can_view_supervisor_dashboard',
            'can_view_management_dashboard'
        ]
    ).delete()


class Migration(migrations.Migration):
    dependencies = [
        ('identity', '0005_alter_userscope_options_userscope_section_and_more'),
    ]

    operations = [
        migrations.RunPython(create_dashboard_permissions, remove_dashboard_permissions),
    ]