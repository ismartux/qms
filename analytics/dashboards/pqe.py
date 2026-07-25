from analytics.services.submission_metrics import SubmissionMetrics


class PQEDashboard:

    @staticmethod
    def build(plant):
        return {
            "trend": SubmissionMetrics.severity_trend(plant),
            "pareto": SubmissionMetrics.pareto_nc(plant, limit=10),
            "template_comparison": SubmissionMetrics.template_comparison(plant),
        }
