from analytics.services.submission_metrics import SubmissionMetrics
from analytics.services.capa_metrics import CAPAMetrics
from analytics.services.hq_metrics import HQMetrics


class ManagementDashboard:

    @staticmethod
    def build(plant=None):
        return {
            "kpis": SubmissionMetrics.kpis(plant),
            "trend": SubmissionMetrics.severity_trend(plant),
            "template_comparison": SubmissionMetrics.template_comparison(plant),
            "capa_summary": CAPAMetrics.summary(plant),
            "plant_comparison": HQMetrics.plant_comparison(),
        }
