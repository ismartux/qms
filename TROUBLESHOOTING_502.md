# 502 Bad Gateway Error - Troubleshooting Guide

## Error Details
- **Error Code**: 502 Bad Gateway
- **Domain**: qms.ismartux.com
- **Timestamp**: 2026-07-27 14:24:38 UTC
- **Cloudflare Status**: Working
- **Host Status**: Error

## What 502 Means
A 502 error indicates that the backend server (Gunicorn/Django) is not responding or has crashed. Nginx (frontend) is working, but it can't get a response from the backend.

## Immediate Steps to Fix

### 1. Check Server Logs
```bash
# SSH into the server
ssh user@qms.ismartux.com

# Check Gunicorn logs
tail -f /path/to/gunicorn.log
# OR
journalctl -u gunicorn -f

# Check Django logs
tail -f /path/to/qms/logs/django.log

# Check Nginx error logs
tail -f /var/log/nginx/error.log
```

### 2. Restart Gunicorn Service
```bash
# Stop the service
sudo systemctl stop gunicorn

# Start the service
sudo systemctl start gunicorn

# OR restart if it exists
sudo systemctl restart gunicorn

# Check status
sudo systemctl status gunicorn
```

### 3. Restart Nginx
```bash
sudo systemctl restart nginx

# Check status
sudo systemctl status nginx
```

### 4. Check for Python Errors
```bash
# Navigate to QMS directory
cd /path/to/qms

# Test Django configuration
python3 manage.py check

# Look for syntax errors
python3 manage.py shell
```

## Common Causes

### Cause 1: Syntax Error in New Code
The dashboard code I added might have a syntax error.

**Check**: Review the following files for errors:
- `apps/qms/ui/views.py` (dashboard_view function)
- `apps/qms/ui/dashboard_services.py`
- `apps/qms/ui/templates/dashboard/*.html`

**Quick Fix**: Temporarily comment out the dashboard view to restore service:

```python
# In apps/qms/ui/urls.py, comment out:
# path("dashboard/", views.dashboard_view, name="dashboard"),
```

### Cause 2: Import Error
Missing imports in the new files.

**Check**: Run this command:
```bash
cd apps/qms
python3 manage.py shell
```

If it fails, there's an import error.

### Cause 3: Database Migration Issue
New migrations might not be applied.

**Fix**:
```bash
cd apps/qms
python3 manage.py migrate
```

### Cause 4: Memory/CPU Exhaustion
Server might be out of resources.

**Check**:
```bash
# Check memory usage
free -h

# Check CPU usage
top -bn1 | head -20

# Check disk space
df -h
```

### Cause 5: Gunicorn Workers Crashed
Workers might have crashed due to an error.

**Fix**:
```bash
# Restart with more workers
sudo systemctl restart gunicorn

# OR increase worker count in gunicorn config
```

## Quick Diagnostic Commands

### Test Django Locally
```bash
cd /path/to/qms
python3 manage.py runserver 0.0.0.0:8000

# In another terminal, test it
curl http://localhost:8000/ui/dashboard/
```

### Check if Port is Listening
```bash
# Check if Gunicorn is listening on the expected port
netstat -tlnp | grep 8000
# OR
ss -tlnp | grep 8000
```

### Verify Nginx Configuration
```bash
# Test nginx config
sudo nginx -t

# Reload nginx
sudo systemctl reload nginx
```

## Immediate Recovery Steps

### Option 1: Quick Rollback (Fastest)
If the dashboard code is causing the issue:

```bash
cd /path/to/qms

# Comment out the dashboard URL temporarily
# Edit apps/qms/ui/urls.py and comment out the dashboard line

# Restart services
sudo systemctl restart gunicorn
sudo systemctl restart nginx
```

### Option 2: Check Specific Errors
```bash
# Run Django in debug mode temporarily
cd /path/to/qms
python3 manage.py runserver 0.0.0.0:8000 --verbosity 3

# Try accessing the dashboard
curl http://localhost:8000/ui/dashboard/
```

### Option 3: View Full Error Trace
```bash
# Check the last 100 lines of gunicorn log
sudo journalctl -u gunicorn -n 100 --no-pager

# OR check Django log
tail -n 100 /path/to/qms/logs/django.log
```

## Prevention for Future

### 1. Use Virtual Environment
```bash
# Ensure you're using the correct Python
source /path/to/venv/bin/activate
```

### 2. Test Before Deploying
```bash
# Always test before restarting
python3 manage.py check
python3 manage.py test
```

### 3. Graceful Restart
```bash
# Use reload instead of restart for zero downtime
sudo systemctl reload gunicorn
```

### 4. Monitor Logs
```bash
# Set up log monitoring
tail -f /path/to/gunicorn.log | grep -i error
```

## Specific Issues in Dashboard Code

### Issue 1: Missing Template Tags
The templates use `{% load custom_filters %}` which might not exist.

**Fix**: Either create the custom_filters or remove that line.

### Issue 2: Missing Icons
Templates use Font Awesome icons which might not be loaded.

**Fix**: Ensure Font Awesome is included in base template.

### Issue 3: Database Query Errors
The dashboard_services.py might have query issues.

**Fix**: Test the service:
```bash
python3 manage.py shell
>>> from ui.dashboard_services import DashboardDataService
>>> # Test with a user
```

## Emergency Rollback Script

Create this script for quick rollback:

```bash
#!/bin/bash
# emergency_rollback.sh

echo "Stopping gunicorn..."
sudo systemctl stop gunicorn

echo "Commenting out dashboard URL..."
sed -i 's/^.*path("dashboard\/".*$/# &/' /path/to/qms/apps/qms/ui/urls.py

echo "Starting gunicorn..."
sudo systemctl start gunicorn

echo "Restarting nginx..."
sudo systemctl restart nginx

echo "Rollback complete. Check if site is up."
```

## After Fixing

### 1. Verify Site is Up
```bash
curl -I https://qms.ismartux.com
```

### 2. Check Logs for Errors
```bash
sudo journalctl -u gunicorn -n 50
```

### 3. Test Dashboard Access
```bash
# Login and navigate to /ui/dashboard/
# Or test directly
curl https://qms.ismartux.com/ui/dashboard/
```

## Contact Information

If the issue persists:
1. Check full error logs
2. Note the exact error message
3. Check when the error started
4. Review recent changes (git log)

## Most Likely Cause

Based on the timing (right after dashboard implementation), the most likely causes are:

1. **Syntax error in views.py** - The dashboard_view function
2. **Import error in dashboard_services.py** - Missing model imports
3. **Template error** - Missing template tags or base template issues

## Quick Test

Run this to check for syntax errors:
```bash
cd /path/to/qms
python3 -m py_compile apps/qms/ui/views.py
python3 -m py_compile apps/qms/ui/dashboard_services.py

# If no errors, check imports
python3 manage.py shell -c "from ui.views import dashboard_view; print('OK')"
```

## Next Steps

1. **Check the logs first** - They will tell you exactly what's wrong
2. **Test Django locally** - Run `python3 manage.py runserver` and test
3. **Fix the specific error** - Don't guess, read the error message
4. **Restart services** - After fixing, restart gunicorn and nginx
5. **Verify** - Check that the site is back up

The code I provided should work, but there might be environment-specific issues (missing packages, database permissions, etc.) that are causing the 502 error.