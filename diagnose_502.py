#!/usr/bin/env python3
"""
Quick diagnostic script to identify 502 error causes
Run this on the server: python3 diagnose_502.py
"""

import sys
import os

# Add the project directory to path
project_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_dir)

print("=" * 60)
print("QMS 502 Error Diagnostic Tool")
print("=" * 60)

# Test 1: Check Python version
print("\n1. Python Version Check")
print(f"   Python: {sys.version}")

# Test 2: Check Django can be imported
print("\n2. Django Import Check")
try:
    import django
    print(f"   ✓ Django {django.VERSION} imported successfully")
except ImportError as e:
    print(f"   ✗ Django import failed: {e}")
    sys.exit(1)

# Test 3: Check settings can be loaded
print("\n3. Settings Check")
try:
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
    django.setup()
    print("   ✓ Settings loaded successfully")
except Exception as e:
    print(f"   ✗ Settings failed: {e}")
    sys.exit(1)

# Test 4: Check dashboard_services.py can be imported
print("\n4. Dashboard Services Import Check")
try:
    from ui.dashboard_services import DashboardDataService
    print("   ✓ DashboardDataService imported successfully")
except Exception as e:
    print(f"   ✗ Dashboard services import failed: {e}")
    print(f"   Error type: {type(e).__name__}")
    import traceback
    traceback.print_exc()

# Test 5: Check views.py can be imported
print("\n5. Views Import Check")
try:
    from ui.views import dashboard_view
    print("   ✓ dashboard_view imported successfully")
except Exception as e:
    print(f"   ✗ Views import failed: {e}")
    print(f"   Error type: {type(e).__name__}")
    import traceback
    traceback.print_exc()

# Test 6: Check models exist
print("\n6. Models Check")
try:
    from submissions.models import Submission, WorkContext
    from scheduler.models import FormSchedule, ScheduledInstance, MissedFormAlert
    from forms_engine.models import ChecklistTemplate
    print("   ✓ All required models imported successfully")
except Exception as e:
    print(f"   ✗ Model import failed: {e}")
    import traceback
    traceback.print_exc()

# Test 7: Check templates can be loaded
print("\n7. Template Check")
try:
    from django.template.loader import get_template
    templates = [
        'dashboard/operator_dashboard.html',
        'dashboard/supervisor_dashboard.html',
        'dashboard/management_dashboard.html',
    ]
    for template_name in templates:
        try:
            get_template(template_name)
            print(f"   ✓ {template_name} - OK")
        except Exception as e:
            print(f"   ✗ {template_name} - FAILED: {e}")
except Exception as e:
    print(f"   ✗ Template system failed: {e}")

# Test 8: Check URL configuration
print("\n8. URL Configuration Check")
try:
    from django.urls import reverse
    # Try to reverse the dashboard URL
    url = reverse('ui:dashboard')
    print(f"   ✓ Dashboard URL resolved: {url}")
except Exception as e:
    print(f"   ✗ URL resolution failed: {e}")

# Test 9: Check database connectivity
print("\n9. Database Check")
try:
    from django.db import connection
    cursor = connection.cursor()
    cursor.execute("SELECT 1")
    print("   ✓ Database connection successful")
except Exception as e:
    print(f"   ✗ Database connection failed: {e}")

# Test 10: Check if user has work context
print("\n10. Work Context Check (Optional)")
try:
    from django.contrib.auth import get_user_model
    User = get_user_model()
    
    # Get first active user
    user = User.objects.filter(is_active=True).first()
    if user:
        from core.identity.context import get_user_scope
        from ui.utils import get_active_context_for_user
        
        work_context = get_active_context_for_user(user)
        if work_context:
            print(f"   ✓ Test user '{user.username}' has work context")
            scope = get_user_scope(user, work_context=work_context)
            if scope and scope.role:
                print(f"   ✓ User has role: {scope.role.name} ({scope.role.code})")
            else:
                print("   ⚠ User has no role assigned")
        else:
            print("   ⚠ Test user has no active work context")
    else:
        print("   ⚠ No active users found")
except Exception as e:
    print(f"   ✗ Work context check failed: {e}")

print("\n" + "=" * 60)
print("Diagnostic Complete")
print("=" * 60)
print("\nIf you see errors above, fix them in this order:")
print("1. Import errors - check missing dependencies")
print("2. Template errors - check template syntax")
print("3. Model errors - check model names and imports")
print("4. Database errors - check database connectivity")
print("\nAfter fixing, restart gunicorn and nginx:")
print("  sudo systemctl restart gunicorn")
print("  sudo systemctl restart nginx")