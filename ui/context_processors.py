"""
Context processors for the UI app
"""
from django.utils import timezone
from django.core.cache import cache
from scheduler.models import MissedFormAlert


def notification_count(request):
    """
    Add notification count to all template contexts (cached for 30 seconds)
    """
    if request.user.is_authenticated:
        cache_key = f"qms_ui_notif_count_{request.user.id}"
        cached_count = cache.get(cache_key)
        if cached_count is not None:
            return {'missed_form_alerts_count': cached_count}

        # Count unread missed form alerts
        missed_count = MissedFormAlert.objects.filter(
            user=request.user,
            notification_sent=False
        ).count()
        
        # Count upcoming reminders
        upcoming_count = MissedFormAlert.objects.filter(
            user=request.user,
            notification_sent=True,
            expected_at__gt=timezone.now()
        ).count()
        
        total_count = missed_count + upcoming_count
        cache.set(cache_key, total_count, 30)
        
        return {
            'missed_form_alerts_count': total_count,
        }
    return {'missed_form_alerts_count': 0}


def admin_panel_context(request):
    """
    Add admin panel context variables to all template contexts
    """
    if request.user.is_authenticated:
        # Define all admin-related app names that should show the admin sidebar
        admin_apps = {
            'admin_panel',
            'accounts',
            'identity',
            'transs_admin_flow',
            'scheduler_admin',
            'ehs_builder',
        }
        
        current_app = request.resolver_match.app_name if request.resolver_match else None
        is_admin_panel = current_app in admin_apps
        
        # Check permission-based access: superuser/staff OR has the can_access_admin_panel permission
        from core.identity.permissions import has_permission
        has_admin_access = (
            request.user.is_superuser or 
            request.user.is_staff or 
            has_permission(request.user, 'can_access_admin_panel')
        )
        
        return {
            'is_admin_panel': is_admin_panel,
            'has_admin_access': has_admin_access,
        }
    return {
        'is_admin_panel': False,
        'has_admin_access': False,
    }
