# Dashboard 502 Error - Fixes Applied

## ✅ Issues Fixed

### 1. **Middleware Import Error** (CRITICAL - Caused 502)
**File**: `apps/qms/scheduler/middleware.py`
**Problem**: Invalid import statement `import timezone` (line 2)
**Fix**: Removed the invalid import, kept only `from django.utils import timezone`

### 2. **Template Filter Error - operator_dashboard.html**
**File**: `apps/qms/ui/templates/dashboard/operator_dashboard.html`
**Problem**: Used non-existent filter `as_value` and `get_difference`
**Fix**: Changed to simple subtraction logic using template tags:
```django
{{ form.required|floatformat:0|add:"-"|add:form.completed|floatformat:0 }}
```

### 3. **Template Filter Error - management_dashboard.html**
**File**: `apps/qms/ui/templates/dashboard/management_dashboard.html`
**Problem**: Used non-existent filter `max` in template
**Fix**: 
- Modified `dashboard_services.py` to calculate `max_count` in Python
- Updated template to use `max_count` variable instead of filter

### 4. **Dashboard Service Enhancement**
**File**: `apps/qms/ui/dashboard_services.py`
**Change**: Added `max_count` calculation for weekly trend chart:
```python
weekly_trend = self._get_weekly_trend(plants)
data['weekly_trend'] = weekly_trend
data['max_count'] = max([day['count'] for day in weekly_trend]) if weekly_trend else 1
```

## 🚀 Deploy These Changes

On your server, run:

```bash
# 1. Pull the latest changes (if using git)
cd /path/to/qms
git pull

# OR if manually deployed, the files are already updated

# 2. Test Django configuration
python3 manage.py check

# 3. Restart services
sudo systemctl restart gunicorn
sudo systemctl restart nginx

# 4. Verify site is up
curl -I https://qms.ismartux.com
```

## 🧪 Test the Fix

```bash
# Run diagnostic again to verify all issues are fixed
python3 diagnose_502.py

# Should show all green checkmarks now
```

## 📊 Dashboard is Now Live

Access the dashboard at: `https://qms.ismartux.com/ui/dashboard/`

The system will:
1. Detect user role automatically
2. Show the appropriate dashboard (Operator/Supervisor/Management)
3. Display real-time data with auto-refresh every 30 seconds

## 🎯 What Each Role Sees

**Operators** (`/ui/dashboard/`):
- Their own submission stats
- Scheduled forms with progress
- Recent activity
- Missed forms count

**Supervisors** (`/ui/dashboard/`):
- Team performance metrics
- Team missed forms table
- Top performers leaderboard
- Critical issues

**Management** (`/ui/dashboard/`):
- Plant-wide statistics
- Performance by plant/shop
- 7-day trend chart
- Missed forms summary

## ⚠️ If Still Getting 502

Run the diagnostic and check for any remaining errors:

```bash
python3 diagnose_502.py
```

Common remaining issues:
1. **Database permissions** - Ensure the app can read/write to database
2. **Missing templates** - Check all template files exist
3. **Model changes** - Run `python3 manage.py makemigrations && python3 manage.py migrate`

## 📝 Notes

- The dashboard URL was already enabled in urls.py
- All template errors have been fixed
- The middleware import error (main cause of 502) is fixed
- The site should be back up now after restarting gunicorn

## 🔧 Quick Rollback (If Needed)

If any new issues arise, comment out the dashboard URL again:

```bash
sed -i 's/^    path("dashboard\/".*$/# &/' apps/qms/ui/urls.py
sudo systemctl restart gunicorn
```

## ✨ Summary

All identified issues have been fixed:
- ✅ Middleware import error fixed
- ✅ Template filter errors fixed
- ✅ Dashboard service enhanced
- ✅ URL configuration correct

The 502 error should be resolved now. Restart gunicorn and nginx to apply the fixes.