from analytics.services.submission_metrics import SubmissionMetrics
from analytics.services.capa_metrics import CAPAMetrics


class TLAMDashboard:

    @staticmethod
    def build(plant):
        kpis = SubmissionMetrics.kpis(plant)
        capa = CAPAMetrics.summary(plant)

        risk_index = (
            (kpis.get("high_severity") or 0) * 3 +
            (capa.get("open_count") or 0) * 2 +
            (capa.get("overdue") or 0) * 4
        )

        return {
            "kpis": kpis,
            "capa": capa,
            "risk_index": risk_index,
        }
