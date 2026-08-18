# Generated migration for forms_engine permissions
from django.db import migrations


def create_forms_engine_permissions(apps, schema_editor):
    """Create forms_engine-related permissions"""
    Permission = apps.get_model('identity', 'Permission')
    
    permissions = [
        # ======================
        # TEMPLATE MANAGEMENT
        # ======================
        {
            'code': 'can_create_form_template',
            'name': 'Can Create Form Template',
            'description': 'Allows creating new form templates'
        },
        {
            'code': 'can_edit_form_template',
            'name': 'Can Edit Form Template',
            'description': 'Allows editing existing form templates'
        },
        {
            'code': 'can_delete_form_template',
            'name': 'Can Delete Form Template',
            'description': 'Allows deleting form templates'
        },
        {
            'code': 'can_view_form_template',
            'name': 'Can View Form Template',
            'description': 'Allows viewing form templates'
        },
        {
            'code': 'can_archive_form_template',
            'name': 'Can Archive Form Template',
            'description': 'Allows archiving form templates'
        },
        
        # ======================
        # VERSION MANAGEMENT
        # ======================
        {
            'code': 'can_publish_form_version',
            'name': 'Can Publish Form Version',
            'description': 'Allows publishing form versions'
        },
        {
            'code': 'can_activate_form_version',
            'name': 'Can Activate Form Version',
            'description': 'Allows activating form versions'
        },
        
        # ======================
        # FORM STRUCTURE MANAGEMENT
        # ======================
        {
            'code': 'can_manage_form_sections',
            'name': 'Can Manage Form Sections',
            'description': 'Allows adding, editing, and deleting form sections'
        },
        {
            'code': 'can_manage_form_items',
            'name': 'Can Manage Form Items',
            'description': 'Allows adding, editing, and deleting form items/questions'
        },
        {
            'code': 'can_manage_form_rules',
            'name': 'Can Manage Form Rules',
            'description': 'Allows adding, editing, and deleting form rules'
        },
        
        # ======================
        # APPROVAL MANAGEMENT
        # ======================
        {
            'code': 'can_manage_approval_flow',
            'name': 'Can Manage Approval Flow',
            'description': 'Allows configuring approval flows for forms'
        },
        {
            'code': 'can_approve_forms',
            'name': 'Can Approve Forms',
            'description': 'Allows approving form submissions'
        },
        
        # ======================
        # ROLE ASSIGNMENT
        # ======================
        {
            'code': 'can_assign_form_roles',
            'name': 'Can Assign Form Roles',
            'description': 'Allows assigning roles to form templates'
        },
        
        # ======================
        # FORM SUBMISSION
        # ======================
        {
            'code': 'can_fill_forms',
            'name': 'Can Fill Forms',
            'description': 'Allows filling out and submitting forms'
        },
        {
            'code': 'can_view_own_submissions',
            'name': 'Can View Own Submissions',
            'description': 'Allows viewing own form submissions'
        },
        {
            'code': 'can_view_all_submissions',
            'name': 'Can View All Submissions',
            'description': 'Allows viewing all form submissions in assigned scope'
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


def remove_forms_engine_permissions(apps, schema_editor):
    """Remove forms_engine permissions"""
    Permission = apps.get_model('identity', 'Permission')
    Permission.objects.filter(
        code__in=[
            'can_create_form_template',
            'can_edit_form_template',
            'can_delete_form_template',
            'can_view_form_template',
            'can_archive_form_template',
            'can_publish_form_version',
            'can_activate_form_version',
            'can_manage_form_sections',
            'can_manage_form_items',
            'can_manage_form_rules',
            'can_manage_approval_flow',
            'can_approve_forms',
            'can_assign_form_roles',
            'can_fill_forms',
            'can_view_own_submissions',
            'can_view_all_submissions',
        ]
    ).delete()


class Migration(migrations.Migration):
    dependencies = [
        ('identity', '0006_dashboard_permissions'),
        ('identity', '0013_approvalcategory_remove_role_category_and_more'),
    ]

    operations = [
        migrations.RunPython(create_forms_engine_permissions, remove_forms_engine_permissions),
    ]
