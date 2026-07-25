# analytics/views/hq_views.py
from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from django.http import JsonResponse
from core.identity.permissions import has_permission
from analytics.services.hq_analytics import HQAnalyticsService
@login_required
def hq_dashboard_view(request):
    """
    View for HQ analytics dashboard.
    """
    if not has_permission(request.user, 'can_view_hq_analytics'):
        from django.core.exceptions import PermissionDenied
        raise PermissionDenied("You don't have permission to view HQ analytics.")
    # Get plant summary data
    plant_summary = HQAnalyticsService.get_plant_summary()
    # Get trend data
    trend_data = HQAnalyticsService.get_trend_data()
    # Get top NC items
    top_nc_items = HQAnalyticsService.get_top_nc_items()
    # Get CAPA performance
    capa_performance = HQAnalyticsService.get_capa_performance()
    return render(
        request,
        'analytics/hq_dashboard.html',
        {
            'plant_summary': plant_summary,
            'trend_data': trend_data,
            'top_nc_items': top_nc_items,
            'capa_performance': capa_performance
        }
    )
@login_required
def hq_plant_summary_api(request):
    """
    API endpoint for plant summary data.
    """
    if not has_permission(request.user, 'can_view_hq_analytics'):
        return JsonResponse({'error': 'Permission denied'}, status=403)
    plant_summary = HQAnalyticsService.get_plant_summary()
    # Format data for JSON response
    data = []
    for item in plant_summary:
        data.append({
            'plant_id': item['plant'].id,
            'plant_name': item['plant'].name,
            'plant_code': item['plant'].code,
            'total_submissions': item['total_submissions'],
            'avg_severity': item['avg_severity'],
            'max_severity': item['max_severity'],
            'min_severity': item['min_severity'],
            'nc_count': item['nc_count'],
            'nc_rate': item['nc_rate'],
            'total_capas': item['total_capas'],
            'open_capas': item['open_capas'],
            'closed_capas': item['closed_capas']
        })
    return JsonResponse({'data': data})
@login_required
def hq_trend_data_api(request):
    """
    API endpoint for trend data.
    """
    if not has_permission(request.user, 'can_view_hq_analytics'):
        return JsonResponse({'error': 'Permission denied'}, status=403)
    period = request.GET.get('period', 'month')
    trend_data = HQAnalyticsService.get_trend_data(period)
    # Format data for JSON response
    data = []
    for item in trend_data:
        data.append({
            'period': item['period'].strftime('%Y-%m-%d'),
            'plant': item['plant'],
            'submission_count': item['submission_count'],
            'avg_severity': item['avg_severity'],
            'nc_count': item['nc_count']
        })
    return JsonResponse({'data': data})
@login_required
def hq_top_nc_items_api(request):
    """
    API endpoint for top NC items.
    """
    if not has_permission(request.user, 'can_view_hq_analytics'):
        return JsonResponse({'error': 'Permission denied'}, status=403)
    limit = int(request.GET.get('limit', 10))
    top_nc_items = HQAnalyticsService.get_top_nc_items(limit)
    return JsonResponse({'data': list(top_nc_items)})
@login_required
def hq_capa_performance_api(request):
    """
    API endpoint for CAPA performance data.
    """
    if not has_permission(request.user, 'can_view_hq_analytics'):
        return JsonResponse({'error': 'Permission denied'}, status=403)
    capa_performance = HQAnalyticsService.get_capa_performance()
    # Format data for JSON response
    data = []
    for item in capa_performance:
        data.append({
            'plant_id': item['plant'].id,
            'plant_name': item['plant'].name,
            'plant_code': item['plant'].code,
            'total_capas': item['total_capas'],
            'closed_capas': item['closed_capas'],
            'open_capas': item['open_capas'],
            'avg_closure_time': item['avg_closure_time'],
            'completion_rate': item['completion_rate']
        })
    return JsonResponse({'data': data})