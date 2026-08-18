"""
Management command to assign forms_engine permissions to roles
Run: python3 manage.py assign_forms_engine_permissions
"""
from django.core.management.base import BaseCommand
from core.identity.models import Role, Permission, RolePermission


class Command(BaseCommand):
    help = 'Assign forms_engine permissions to roles'

    def handle(self, *args, **options):
        self.stdout.write('Assigning forms_engine permissions to roles...')
        
        # Define role-permission mappings based on typical QMS hierarchy
        role_permissions = {
            # ======================
            # OPERATORS - Can fill forms and view own submissions
            # ======================
            'OPERATOR': [
                'can_fill_forms',
                'can_view_own_submissions',
            ],
            'IPQC_OPERATOR': [
                'can_fill_forms',
                'can_view_own_submissions',
            ],
            'OQC_OPERATOR': [
                'can_fill_forms',
                'can_view_own_submissions',
            ],
            'FQC_OPERATOR': [
                'can_fill_forms',
                'can_view_own_submissions',
            ],
            
            # ======================
            # SUPERVISORS - Can fill forms, view all submissions, and approve
            # ======================
            'SUPERVISOR': [
                'can_fill_forms',
                'can_view_own_submissions',
                'can_view_all_submissions',
                'can_approve_forms',
            ],
            'LEADER': [
                'can_fill_forms',
                'can_view_own_submissions',
                'can_view_all_submissions',
                'can_approve_forms',
            ],
            'SHOP_SUPERVISOR': [
                'can_fill_forms',
                'can_view_own_submissions',
                'can_view_all_submissions',
                'can_approve_forms',
            ],
            'LINE_LEADER': [
                'can_fill_forms',
                'can_view_own_submissions',
                'can_view_all_submissions',
                'can_approve_forms',
            ],
            
            # ======================
            # MANAGERS - Full forms management capabilities + admin panel
            # ======================
            'MANAGER': [
                'can_fill_forms',
                'can_view_own_submissions',
                'can_view_all_submissions',
                'can_approve_forms',
                'can_view_form_template',
                'can_create_form_template',
                'can_edit_form_template',
                'can_archive_form_template',
                'can_publish_form_version',
                'can_activate_form_version',
                'can_manage_form_sections',
                'can_manage_form_items',
                'can_manage_form_rules',
                'can_manage_approval_flow',
                'can_assign_form_roles',
                'can_access_admin_panel',
            ],
            'PLANT_MANAGER': [
                'can_fill_forms',
                'can_view_own_submissions',
                'can_view_all_submissions',
                'can_approve_forms',
                'can_view_form_template',
                'can_create_form_template',
                'can_edit_form_template',
                'can_archive_form_template',
                'can_delete_form_template',
                'can_publish_form_version',
                'can_activate_form_version',
                'can_manage_form_sections',
                'can_manage_form_items',
                'can_manage_form_rules',
                'can_manage_approval_flow',
                'can_assign_form_roles',
                'can_access_admin_panel',
            ],
            'QUALITY_MANAGER': [
                'can_fill_forms',
                'can_view_own_submissions',
                'can_view_all_submissions',
                'can_approve_forms',
                'can_view_form_template',
                'can_create_form_template',
                'can_edit_form_template',
                'can_archive_form_template',
                'can_delete_form_template',
                'can_publish_form_version',
                'can_activate_form_version',
                'can_manage_form_sections',
                'can_manage_form_items',
                'can_manage_form_rules',
                'can_manage_approval_flow',
                'can_assign_form_roles',
                'can_access_admin_panel',
            ],
            
            # ======================
            # ADMIN - Full access including delete + admin panel
            # ======================
            'ADMIN': [
                'can_fill_forms',
                'can_view_own_submissions',
                'can_view_all_submissions',
                'can_approve_forms',
                'can_view_form_template',
                'can_create_form_template',
                'can_edit_form_template',
                'can_archive_form_template',
                'can_delete_form_template',
                'can_publish_form_version',
                'can_activate_form_version',
                'can_manage_form_sections',
                'can_manage_form_items',
                'can_manage_form_rules',
                'can_manage_approval_flow',
                'can_assign_form_roles',
                'can_access_admin_panel',
            ],
        }
        
        # Get all permissions (forms_engine + admin panel)
        permission_codes = [
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
            'can_access_admin_panel',
        ]
        
        permissions = {
            perm.code: perm 
            for perm in Permission.objects.filter(code__in=permission_codes)
        }
        
        if not permissions:
            self.stdout.write(self.style.WARNING(
                'Forms engine permissions not found. Please run migrations first:'
                '\n  python3 manage.py migrate'
            ))
            return
        
        self.stdout.write(f'Found {len(permissions)} permissions')
        
        # Assign permissions to roles
        assigned_count = 0
        
        for role_code, perm_codes in role_permissions.items():
            try:
                role = Role.objects.get(code=role_code)
                
                for perm_code in perm_codes:
                    if perm_code in permissions:
                        permission = permissions[perm_code]
                        
                        # Create role-permission mapping
                        role_perm, created = RolePermission.objects.get_or_create(
                            role=role,
                            permission=permission
                        )
                        
                        if created:
                            assigned_count += 1
                            self.stdout.write(
                                f'  ✓ Assigned "{permission.name}" to "{role.name}"'
                            )
                
            except Role.DoesNotExist:
                self.stdout.write(
                    self.style.WARNING(f'  ⚠ Role "{role_code}" not found, skipping...')
                )
                continue
        
        self.stdout.write(
            self.style.SUCCESS(
                f'\n✓ Successfully assigned {assigned_count} role-permission mappings'
            )
        )
        
        # Summary
        self.stdout.write('\nPermissions Access Summary:')
        self.stdout.write('  Operators:  Fill forms, view own submissions')
        self.stdout.write('  Supervisors: Fill forms, view all submissions, approve forms')
        self.stdout.write('  Managers: Full form management + Admin Panel access')
        self.stdout.write('  Admin: Full access including delete + Admin Panel access')
        self.stdout.write('  Superusers: Full access (automatic)')