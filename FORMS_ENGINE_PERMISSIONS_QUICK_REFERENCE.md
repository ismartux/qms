# Forms Engine Permissions - Quick Reference

## Created Permissions (16 Total)

### Template Management
- `can_create_form_template` - Create new form templates
- `can_edit_form_template` - Edit existing form templates
- `can_delete_form_template` - Delete form templates
- `can_view_form_template` - View form templates
- `can_archive_form_template` - Archive form templates

### Version Management
- `can_publish_form_version` - Publish form versions
- `can_activate_form_version` - Activate form versions

### Form Structure
- `can_manage_form_sections` - Manage form sections
- `can_manage_form_items` - Manage form items/questions
- `can_manage_form_rules` - Manage form rules

### Approval Management
- `can_manage_approval_flow` - Configure approval flows
- `can_approve_forms` - Approve form submissions

### Role Assignment
- `can_assign_form_roles` - Assign roles to form templates

### Form Submission
- `can_fill_forms` - Fill out and submit forms
- `can_view_own_submissions` - View own submissions
- `can_view_all_submissions` - View all submissions in scope

## Setup Steps

### 1. Migrations (Already Done ✅)
```bash
cd apps/qms
python3 manage.py migrate
```

### 2. Create Roles (If Not Already Created)
```bash
python3 manage.py shell
```

```python
from core.identity.models import Role

# Create basic roles
roles = [
    ('OPERATOR', 'Operator'),
    ('IPQC_OPERATOR', 'IPQC Operator'),
    ('OQC_OPERATOR', 'OQC Operator'),
    ('FQC_OPERATOR', 'FQC Operator'),
    ('SUPERVISOR', 'Supervisor'),
    ('LEADER', 'Leader'),
    ('SHOP_SUPERVISOR', 'Shop Supervisor'),
    ('LINE_LEADER', 'Line Leader'),
    ('MANAGER', 'Manager'),
    ('PLANT_MANAGER', 'Plant Manager'),
    ('QUALITY_MANAGER', 'Quality Manager'),
    ('ADMIN', 'Admin'),
]

for code, name in roles:
    role, created = Role.objects.get_or_create(
        code=code,
        defaults={'name': name, 'is_active': True}
    )
    if created:
        print(f'Created role: {code}')
    else:
        print(f'Role already exists: {code}')
```

### 3. Assign Permissions to Roles
```bash
python3 manage.py assign_forms_engine_permissions
```

### 4. Verify Setup
```bash
python3 manage.py shell
```

```python
from core.identity.models import Role, Permission, RolePermission

# Check permissions for a role
role = Role.objects.get(code='OPERATOR')
perms = RolePermission.objects.filter(role=role).select_related('permission')
print(f"\n{role.name} permissions:")
for rp in perms:
    print(f"  ✓ {rp.permission.code}")

# Check all forms_engine permissions
print("\nAll forms_engine permissions:")
for perm in Permission.objects.filter(code__in=[
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
]):
    print(f"  {perm.code}: {perm.name}")
```

## Using Permissions in Code

### In Views
```python
from core.identity.permissions import has_permission
from django.shortcuts import redirect

def create_template_view(request):
    if not has_permission(request.user, 'can_create_form_template'):
        return redirect('transs_admin_flow:form_builder_dashboard')
    
    # User has permission, proceed with template creation
    ...
```

### Custom Decorator
```python
from django.shortcuts import redirect
from core.identity.permissions import has_permission

def forms_engine_permission_required(permission_code):
    def decorator(view_func):
        def wrapper(request, *args, **kwargs):
            if not has_permission(request.user, permission_code):
                return redirect('transs_admin_flow:form_builder_dashboard')
            return view_func(request, *args, **kwargs)
        return wrapper
    return decorator

# Usage
@login_required
@forms_engine_permission_required('can_edit_form_template')
def edit_template(request, template_id):
    ...
```

### In Templates
```django
{% load access_tags %}

{% if perms.can_create_form_template %}
    <a href="{% url 'transs_admin_flow:create_template' %}" class="btn btn-primary">
        Create New Template
    </a>
{% endif %}

{% if perms.can_edit_form_template %}
    <a href="{% url 'transs_admin_flow:edit_template' template.id %}" class="btn btn-secondary">
        Edit
    </a>
{% endif %}

{% if perms.can_delete_form_template %}
    <button class="btn btn-danger" onclick="deleteTemplate({{ template.id }})">
        Delete
    </button>
{% endif %}

{% if perms.can_approve_forms %}
    <button class="btn btn-success" onclick="approveForm({{ submission.id }})">
        Approve
    </button>
{% endif %}
```

### Checking Multiple Permissions
```python
from core.identity.permissions import has_permission

def template_detail_view(request, template_id):
    user_perms = {
        'can_edit': has_permission(request.user, 'can_edit_form_template'),
        'can_delete': has_permission(request.user, 'can_delete_form_template'),
        'can_publish': has_permission(request.user, 'can_publish_form_version'),
        'can_approve': has_permission(request.user, 'can_approve_forms'),
    }
    
    return render(request, 'template_detail.html', {
        'template': template,
        'permissions': user_perms,
    })
```

## Permission Matrix by Role

| Permission | Operator | Supervisor | Manager | Admin |
|------------|----------|------------|---------|-------|
| can_fill_forms | ✓ | ✓ | ✓ | ✓ |
| can_view_own_submissions | ✓ | ✓ | ✓ | ✓ |
| can_view_all_submissions | | ✓ | ✓ | ✓ |
| can_approve_forms | | ✓ | ✓ | ✓ |
| can_view_form_template | | | ✓ | ✓ |
| can_create_form_template | | | ✓ | ✓ |
| can_edit_form_template | | | ✓ | ✓ |
| can_archive_form_template | | | ✓ | ✓ |
| can_delete_form_template | | | | ✓ |
| can_publish_form_version | | | ✓ | ✓ |
| can_activate_form_version | | | ✓ | ✓ |
| can_manage_form_sections | | | ✓ | ✓ |
| can_manage_form_items | | | ✓ | ✓ |
| can_manage_form_rules | | | ✓ | ✓ |
| can_manage_approval_flow | | | ✓ | ✓ |
| can_assign_form_roles | | | ✓ | ✓ |

## Troubleshooting

### Permission Not Working
1. Check user has UserScope with appropriate role
2. Verify RolePermission mapping exists
3. Ensure permission code is correct (snake_case)
4. Superusers bypass all checks

### View Current User's Permissions
```bash
python3 manage.py shell
```

```python
from django.contrib.auth import get_user_model
from core.identity.permissions import has_permission

User = get_user_model()
user = User.objects.get(username='your_username')

print(f"\nPermissions for {user.username}:")
for perm_code in [
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
]:
    has_perm = has_permission(user, perm_code)
    status = '✓' if has_perm else '✗'
    print(f"  {status} {perm_code}")
```

## Files Created

1. `apps/qms/core/identity/migrations/0014_forms_engine_permissions.py` - Migration
2. `apps/qms/core/identity/management/commands/assign_forms_engine_permissions.py` - Management command
3. `apps/qms/FORMS_ENGINE_PERMISSIONS_SETUP.md` - Full documentation
4. `apps/qms/FORMS_ENGINE_PERMISSIONS_QUICK_REFERENCE.md` - This file

## Next Steps

1. ✅ Migrations applied
2. ✅ Permissions created (16 total)
3. ⏭️ Create roles (if not already created)
4. ⏭️ Run `assign_forms_engine_permissions` command
5. ⏭️ Update forms_engine views to use permission checks
6. ⏭️ Update templates to show/hide buttons based on permissions