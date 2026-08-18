# Forms Engine Role Permissions Setup

This document describes the role-based permission system for the forms_engine module.

## Overview

The forms_engine uses Django's permission system with Role-Based Access Control (RBAC). Permissions are assigned to roles, and users gain permissions through their role assignments in specific plants (UserScope).

## Permission Categories

### 1. Template Management
- `can_create_form_template` - Create new form templates
- `can_edit_form_template` - Edit existing form templates
- `can_delete_form_template` - Delete form templates
- `can_view_form_template` - View form templates
- `can_archive_form_template` - Archive form templates

### 2. Version Management
- `can_publish_form_version` - Publish form versions
- `can_activate_form_version` - Activate form versions

### 3. Form Structure Management
- `can_manage_form_sections` - Manage form sections
- `can_manage_form_items` - Manage form items/questions
- `can_manage_form_rules` - Manage form rules

### 4. Approval Management
- `can_manage_approval_flow` - Configure approval flows
- `can_approve_forms` - Approve form submissions

### 5. Role Assignment
- `can_assign_form_roles` - Assign roles to form templates

### 6. Form Submission
- `can_fill_forms` - Fill out and submit forms
- `can_view_own_submissions` - View own submissions
- `can_view_all_submissions` - View all submissions in scope

## Role-Based Access Matrix

### Operators (OPERATOR, IPQC_OPERATOR, OQC_OPERATOR, FQC_OPERATOR)
```
✓ can_fill_forms
✓ can_view_own_submissions
```

### Supervisors (SUPERVISOR, LEADER, SHOP_SUPERVISOR, LINE_LEADER)
```
✓ can_fill_forms
✓ can_view_own_submissions
✓ can_view_all_submissions
✓ can_approve_forms
```

### Managers (MANAGER, PLANT_MANAGER, QUALITY_MANAGER)
```
✓ can_fill_forms
✓ can_view_own_submissions
✓ can_view_all_submissions
✓ can_approve_forms
✓ can_view_form_template
✓ can_create_form_template
✓ can_edit_form_template
✓ can_archive_form_template
✓ can_publish_form_version
✓ can_activate_form_version
✓ can_manage_form_sections
✓ can_manage_form_items
✓ can_manage_form_rules
✓ can_manage_approval_flow
✓ can_assign_form_roles
```

### Admin (ADMIN)
```
✓ can_fill_forms
✓ can_view_own_submissions
✓ can_view_all_submissions
✓ can_approve_forms
✓ can_view_form_template
✓ can_create_form_template
✓ can_edit_form_template
✓ can_archive_form_template
✓ can_delete_form_template
✓ can_publish_form_version
✓ can_activate_form_version
✓ can_manage_form_sections
✓ can_manage_form_items
✓ can_manage_form_rules
✓ can_manage_approval_flow
✓ can_assign_form_roles
```

### Superusers
- Full access to all permissions (automatic bypass)

## Setup Instructions

### Step 1: Run Migrations

Create the permissions in the database:

```bash
python3 manage.py migrate
```

This will execute the migration `0007_forms_engine_permissions.py` which creates all 16 forms_engine permissions.

### Step 2: Assign Permissions to Roles

Run the management command to assign permissions to roles:

```bash
python3 manage.py assign_forms_engine_permissions
```

This will:
1. Find all forms_engine permissions
2. Assign them to the appropriate roles based on the access matrix
3. Create RolePermission mappings in the database

### Step 3: Verify Setup

Check that permissions were assigned correctly:

```bash
python3 manage.py shell
```

```python
from core.identity.models import Role, Permission, RolePermission

# Check a specific role's permissions
role = Role.objects.get(code='OPERATOR')
perms = RolePermission.objects.filter(role=role).select_related('permission')
for rp in perms:
    print(f"  - {rp.permission.code}")

# Check all permissions
print("\nAll forms_engine permissions:")
for perm in Permission.objects.filter(code__startswith='can_'):
    print(f"  {perm.code}: {perm.name}")
```

## Using Permissions in Code

### Checking Permissions

Use the `has_permission` function from `core.identity.permissions`:

```python
from core.identity.permissions import has_permission

def my_view(request):
    if has_permission(request.user, 'can_create_form_template'):
        # User can create templates
        pass
    else:
        # User cannot create templates
        pass
```

### Using Decorators

Create custom decorators for forms_engine views:

```python
from django.shortcuts import redirect
from core.identity.permissions import has_permission

def can_manage_templates(view_func):
    def wrapper(request, *args, **kwargs):
        if not has_permission(request.user, 'can_edit_form_template'):
            return redirect('transs_admin_flow:form_builder_dashboard')
        return view_func(request, *args, **kwargs)
    return wrapper
```

### In Templates

Use the permission check in templates:

```django
{% if perms.can_edit_form_template %}
    <a href="{% url 'transs_admin_flow:edit_template' template.id %}">Edit</a>
{% endif %}
```

## Modifying Permissions

### Adding New Permissions

1. Add the permission to the migration file `0007_forms_engine_permissions.py`
2. Update the management command `assign_forms_engine_permissions.py`
3. Run migrations: `python3 manage.py migrate`
4. Run the management command: `python3 manage.py assign_forms_engine_permissions`

### Changing Role Assignments

Edit the `role_permissions` dictionary in `assign_forms_engine_permissions.py` and re-run the command:

```bash
python3 manage.py assign_forms_engine_permissions
```

The command uses `get_or_create`, so it won't duplicate existing mappings.

## Architecture

```
User → UserScope (user + plant + role) → Role → RolePermission → Permission
```

- **User**: Django user model
- **UserScope**: Links user to a plant with a specific role
- **Role**: Defines a set of permissions (e.g., OPERATOR, MANAGER)
- **RolePermission**: Many-to-many mapping between Role and Permission
- **Permission**: Individual permission (e.g., can_create_form_template)

## Files Created

1. `apps/qms/core/identity/migrations/0007_forms_engine_permissions.py` - Migration to create permissions
2. `apps/qms/core/identity/management/commands/assign_forms_engine_permissions.py` - Management command to assign permissions
3. `apps/qms/FORMS_ENGINE_PERMISSIONS_SETUP.md` - This documentation file

## Related Files

- `apps/qms/core/identity/models.py` - Permission, Role, RolePermission models
- `apps/qms/core/identity/permissions.py` - has_permission() function
- `apps/qms/core/identity/migrations/0006_dashboard_permissions.py` - Example of dashboard permissions
- `apps/qms/core/identity/management/commands/assign_dashboard_permissions.py` - Example of dashboard permission assignment

## Troubleshooting

### Permissions not found

If you get "Permissions not found" error:
1. Ensure migrations have been run: `python3 manage.py migrate`
2. Check that migration `0007_forms_engine_permissions.py` exists
3. Verify the Permission model is in the `identity` app

### Role not found

If you get "Role not found" warnings:
1. Check that the role exists in the database
2. Verify the role code matches exactly (case-sensitive)
3. Create the role if it doesn't exist

### Permission not working

If permissions aren't being enforced:
1. Ensure the user has a UserScope with the appropriate role
2. Check that the RolePermission mapping exists
3. Verify the permission code is correct (snake_case)
4. Superusers bypass all permission checks