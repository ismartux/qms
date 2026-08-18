# Dashboard Permission-Based Access - Setup Guide

## ✅ Implementation Complete

The dashboard system now uses **permission-based access control** integrated with the existing role-based permission system in `core/identity`.

---

## 🔐 Permission Structure

### Three Dashboard Permissions Created

1. **`can_view_operator_dashboard`**
   - Access to Operator Dashboard
   - Personal metrics, scheduled forms, recent submissions

2. **`can_view_supervisor_dashboard`**
   - Access to Supervisor Dashboard
   - Team metrics, missed forms, top performers

3. **`can_view_management_dashboard`**
   - Access to Management Dashboard
   - Plant-wide analytics, trends, shop breakdown

---

## 👥 Role-Based Dashboard Access

### Automatic Permission Assignment

| Role | Operator Dashboard | Supervisor Dashboard | Management Dashboard |
|------|-------------------|---------------------|---------------------|
| **OPERATOR** | ✓ | ✗ | ✗ |
| **IPQC_OPERATOR** | ✓ | ✗ | ✗ |
| **OQC_OPERATOR** | ✓ | ✗ | ✗ |
| **FQC_OPERATOR** | ✓ | ✗ | ✗ |
| **SUPERVISOR** | ✓ | ✓ | ✗ |
| **LEADER** | ✓ | ✓ | ✗ |
| **SHOP_SUPERVISOR** | ✓ | ✓ | ✗ |
| **LINE_LEADER** | ✓ | ✓ | ✗ |
| **MANAGER** | ✓ | ✓ | ✓ |
| **PLANT_MANAGER** | ✓ | ✓ | ✓ |
| **QUALITY_MANAGER** | ✓ | ✓ | ✓ |
| **ADMIN** | ✓ | ✓ | ✓ |
| **Superuser** | ✓ | ✓ | ✓ |

**Note**: Superusers automatically get access to all dashboards without needing explicit permissions.

---

## 🚀 Setup Instructions

### Step 1: Run Migrations

```bash
cd /path/to/qms
python3 manage.py migrate
```

This creates the three dashboard permissions in the database.

### Step 2: Assign Permissions to Roles

Run the management command:

```bash
python3 manage.py assign_dashboard_permissions
```

Expected output:
```
Assigning dashboard permissions to roles...
Found 3 dashboard permissions
  ✓ Assigned "Can View Operator Dashboard" to "Operator"
  ✓ Assigned "Can View Operator Dashboard" to "IPQC Operator"
  ✓ Assigned "Can View Operator Dashboard" to "Supervisor"
  ✓ Assigned "Can View Supervisor Dashboard" to "Supervisor"
  ✓ Assigned "Can View Operator Dashboard" to "Manager"
  ✓ Assigned "Can View Supervisor Dashboard" to "Manager"
  ✓ Assigned "Can View Management Dashboard" to "Manager"
  
✓ Successfully assigned 12 role-permission mappings

Dashboard Access Summary:
  Operators:  Operator Dashboard
  Supervisors: Operator + Supervisor Dashboards
  Management: All Dashboards (Operator + Supervisor + Management)
  Superusers: All Dashboards (automatic)
```

### Step 3: Restart Services

```bash
sudo systemctl restart gunicorn
sudo systemctl restart nginx
```

### Step 4: Test Access

Login as different users and navigate to `/ui/dashboard/`:
- Operators should see Operator Dashboard
- Supervisors should see Supervisor Dashboard
- Management should see Management Dashboard

---

## 🔧 How It Works

### Permission Check Flow

```python
# In ui/views.py - dashboard_view()
if request.user.is_superuser:
    # Superusers get all permissions
    can_view_operator = True
    can_view_supervisor = True
    can_view_management = True
else:
    # Check permissions from role
    can_view_operator = has_permission(request.user, 'can_view_operator_dashboard')
    can_view_supervisor = has_permission(request.user, 'can_view_supervisor_dashboard')
    can_view_management = has_permission(request.user, 'can_view_management_dashboard')

# Show highest-level dashboard user has access to
if can_view_management:
    template = "dashboard/management_dashboard.html"
elif can_view_supervisor:
    template = "dashboard/supervisor_dashboard.html"
else:
    template = "dashboard/operator_dashboard.html"
```

### Permission Resolution

The `has_permission()` function in `core/identity/permissions.py`:
1. Checks if user is superuser (bypass all checks)
2. Gets user's scopes (work context roles)
3. Loads permissions from role assignments
4. Caches permissions for the request
5. Returns True if permission is granted

---

## 🎯 Dashboard Selection Logic

### Hierarchical Access

Users see the **highest-level dashboard** they have permission to access:

```
Management Permission → Shows Management Dashboard
    ↓ (if no management permission)
Supervisor Permission → Shows Supervisor Dashboard
    ↓ (if no supervisor permission)
Operator Permission → Shows Operator Dashboard
```

### Example Scenarios

**Scenario 1: Operator logs in**
- Has: `can_view_operator_dashboard`
- Sees: Operator Dashboard

**Scenario 2: Supervisor logs in**
- Has: `can_view_operator_dashboard`, `can_view_supervisor_dashboard`
- Sees: Supervisor Dashboard (highest level)

**Scenario 3: Manager logs in**
- Has: All three permissions
- Sees: Management Dashboard (highest level)

**Scenario 4: Superuser logs in**
- Has: All permissions (automatic)
- Sees: Management Dashboard (highest level)

---

## 🔨 Customization

### Changing Role Permissions

To modify which roles can access which dashboards, edit the management command:

```python
# In assign_dashboard_permissions.py
role_permissions = {
    # Example: Give operators access to supervisor dashboard
    'OPERATOR': [
        'can_view_operator_dashboard',
        'can_view_supervisor_dashboard',  # Add this
    ],
}
```

Then re-run the command:
```bash
python3 manage.py assign_dashboard_permissions
```

### Adding New Roles

If you add new roles, update the `role_permissions` dictionary in the management command:

```python
role_permissions = {
    # ... existing roles ...
    'NEW_ROLE': ['can_view_operator_dashboard'],  # Add new role
}
```

### Creating Custom Permission Assignments

For fine-grained control, you can assign permissions directly in Django admin:

1. Go to `/admin/identity/role/`
2. Select a role
3. Add dashboard permissions to the role
4. Save

Or via Django shell:
```python
from core.identity.models import Role, Permission, RolePermission

role = Role.objects.get(code='SUPERVISOR')
perm = Permission.objects.get(code='can_view_management_dashboard')

# Grant permission
RolePermission.objects.create(role=role, permission=perm)

# Revoke permission
RolePermission.objects.filter(role=role, permission=perm).delete()
```

---

## 🔍 Troubleshooting

### User Can't Access Expected Dashboard

**Check 1: Verify permissions exist**
```bash
python3 manage.py shell
>>> from core.identity.models import Permission
>>> Permission.objects.filter(code__startswith='can_view_').values_list('code', flat=True)
```

**Check 2: Verify role has permissions**
```bash
>>> from core.identity.models import Role, RolePermission
>>> role = Role.objects.get(code='SUPERVISOR')
>>> role.role_permissions.values_list('permission__code', flat=True)
```

**Check 3: Verify user's role**
```bash
>>> from core.identity.context import get_user_scope
>>> user = User.objects.get(username='operator1')
>>> scope = get_user_scope(user, work_context=...)
>>> scope.role.code
```

**Check 4: Test permission check**
```bash
>>> from core.identity.permissions import has_permission
>>> user = User.objects.get(username='supervisor1')
>>> has_permission(user, 'can_view_supervisor_dashboard')
```

### Common Issues

**Issue: "Dashboard permissions not found"**
- **Solution**: Run migrations: `python3 manage.py migrate`

**Issue: "Role not found"**
- **Solution**: Create the role first in Django admin or via migration

**Issue: "User sees wrong dashboard"**
- **Solution**: Check user's role assignments and permissions

---

## 📊 Dashboard URL

All users access the dashboard at:
```
/ui/dashboard/
```

The system automatically:
1. Detects user's permissions
2. Determines highest accessible dashboard
3. Renders appropriate template
4. Passes all required data

---

## 🔐 Security Features

### Permission-Based Access Control

- ✅ Integrates with existing permission system
- ✅ Role-based permission assignment
- ✅ Superuser bypass (automatic access)
- ✅ Request-level permission caching
- ✅ No hardcoded role checks in views

### Audit Trail

All permission assignments are tracked via:
- `RolePermission` model (who has what)
- Permission changes logged in Django admin
- User scopes tracked in `UserScope` model

---

## 📝 Files Modified/Created

### Core Implementation
| File | Purpose |
|------|---------|
| `core/identity/migrations/0006_dashboard_permissions.py` | Creates dashboard permissions |
| `ui/views.py` | Updated `dashboard_view()` to use permissions |
| `ui/dashboard_services.py` | Dashboard data aggregation (unchanged) |

### Templates (unchanged)
| File | Purpose |
|------|---------|
| `ui/templates/dashboard/operator_dashboard.html` | Operator view |
| `ui/templates/dashboard/supervisor_dashboard.html` | Supervisor view |
| `ui/templates/dashboard/management_dashboard.html` | Management view |

### Management Command
| File | Purpose |
|------|---------|
| `core/identity/management/commands/assign_dashboard_permissions.py` | Assigns permissions to roles |

---

## ✨ Benefits

### For Administrators
- ✅ Centralized permission management
- ✅ Easy to assign/revoke dashboard access
- ✅ Consistent with existing permission system
- ✅ No code changes needed for role updates

### For Users
- ✅ Automatic dashboard selection
- ✅ No manual configuration needed
- ✅ Access only to relevant dashboard
- ✅ Superusers see all dashboards

### For Developers
- ✅ Clean permission-based architecture
- ✅ Reusable permission system
- ✅ Easy to extend with new dashboards
- ✅ Well-documented and maintainable

---

## 🎯 Next Steps

1. **Run migrations**: `python3 manage.py migrate`
2. **Assign permissions**: `python3 manage.py assign_dashboard_permissions`
3. **Restart services**: `sudo systemctl restart gunicorn nginx`
4. **Test access**: Login as different roles and verify dashboard access
5. **Customize if needed**: Adjust role-permission mappings in the management command

---

## 📞 Support

If you need to:
- Add new dashboard permissions → Update migration + management command
- Change role assignments → Edit `role_permissions` dict in management command
- Add new roles → Add to `role_permissions` dict
- Debug access issues → Use the troubleshooting section above

The permission system is now fully integrated and ready for production use!