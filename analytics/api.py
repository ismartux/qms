from django.http import JsonResponse
from analytics.services.pareto import pareto_defects
from analytics.services.severity import severity_distribution
from analytics.services.trends import submission_trends
from analytics.services.summary import summary_kpis
from analytics.services.trends import trend_by_day_and_shift
from analytics.services.pareto import pareto_by_item


def dashboard_metrics_api(request):
    return JsonResponse({
        "summary": summary_kpis(),
        "pareto": pareto_defects(),
        "severity": severity_distribution(),
        "trends": submission_trends(),
    })


def pareto_api(request):
    data = list(pareto_by_item())
    return JsonResponse(data, safe=False)


def trend_api(request):
    data = list(trend_by_day_and_shift())
    return JsonResponse(data, safe=False)