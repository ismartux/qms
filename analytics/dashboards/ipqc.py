from analytics.services.submission_metrics import SubmissionMetrics
from analytics.services.capa_metrics import CAPAMetrics


class IPQCDashboard:

    @staticmethod
    def build(plant):
        return {
            "kpis": SubmissionMetrics.kpis(plant),
            "trend": SubmissionMetrics.severity_trend(plant),
            "capa_summary": CAPAMetrics.summary(plant),
        }
