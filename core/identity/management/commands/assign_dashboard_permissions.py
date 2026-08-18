"""
Management command to assign dashboard permissions to roles
Run: python3 manage.py assign_dashboard_permissions
"""
from django.core.management.base import BaseCommand
from core.identity.models import Role, Permission, RolePermission


class Command(BaseCommand):
    help = 'Assign dashboard permissions to roles'

    def handle(self, *args, **options):
        self.stdout.write('Assigning dashboard permissions to roles...')
        
        # Define role-permission mappings
        role_permissions = {
            # Operators get operator dashboard
            'OPERATOR': ['can_view_operator_dashboard'],
            'IPQC_OPERATOR': ['can_view_operator_dashboard'],
            'OQC_OPERATOR': ['can_view_operator_dashboard'],
            'FQC_OPERATOR': ['can_view_operator_dashboard'],
            
            # Supervisors get operator + supervisor dashboards
            'SUPERVISOR': ['can_view_operator_dashboard', 'can_view_supervisor_dashboard'],
            'LEADER': ['can_view_operator_dashboard', 'can_view_supervisor_dashboard'],
            'SHOP_SUPERVISOR': ['can_view_operator_dashboard', 'can_view_supervisor_dashboard'],
            'LINE_LEADER': ['can_view_operator_dashboard', 'can_view_supervisor_dashboard'],
            
            # Management gets all dashboards
            'MANAGER': ['can_view_operator_dashboard', 'can_view_supervisor_dashboard', 'can_view_management_dashboard'],
            'PLANT_MANAGER': ['can_view_operator_dashboard', 'can_view_supervisor_dashboard', 'can_view_management_dashboard'],
            'QUALITY_MANAGER': ['can_view_operator_dashboard', 'can_view_supervisor_dashboard', 'can_view_management_dashboard'],
            'ADMIN': ['can_view_operator_dashboard', 'can_view_supervisor_dashboard', 'can_view_management_dashboard'],
        }
        
        # Get all permissions
        permissions = {
            perm.code: perm 
            for perm in Permission.objects.filter(
                code__in=[
                    'can_view_operator_dashboard',
                    'can_view_supervisor_dashboard',
                    'can_view_management_dashboard'
                ]
            )
        }
        
        if not permissions:
            self.stdout.write(self.style.WARNING(
                'Dashboard permissions not found. Please run migrations first:'
                '\n  python3 manage.py migrate'
            ))
            return
        
        self.stdout.write(f'Found {len(permissions)} dashboard permissions')
        
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
        self.stdout.write('\nDashboard Access Summary:')
        self.stdout.write('  Operators:  Operator Dashboard')
        self.stdout.write('  Supervisors: Operator + Supervisor Dashboards')
        self.stdout.write('  Management: All Dashboards (Operator + Supervisor + Management)')
        self.stdout.write('  Superusers: All Dashboards (automatic)')