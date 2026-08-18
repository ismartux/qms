from django.http import HttpResponseForbidden
from functools import wraps

def admin_required(view_func):
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        # Allow access if user is staff, superuser, OR has the can_access_admin_panel permission
        if request.user.is_staff or request.user.is_superuser:
            return view_func(request, *args, **kwargs)
        
        # Check for the admin panel permission
        from core.identity.permissions import has_permission
        if has_permission(request.user, 'can_access_admin_panel'):
            return view_func(request, *args, **kwargs)
        
        return HttpResponseForbidden("Admin access required")
    return wrapper
