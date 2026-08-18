from django.db.models import Count, Avg
from django.db.models.functions import TruncMonth
from submissions.models import Submission


class HQMetrics:

    @staticmethod
    def plant_comparison():
        return (
            Submission.objects
            .filter(workflow_state="SUBMITTED")
            .values("plant__name")
            .annotate(
                total=Count("pk"),
                avg_severity=Avg("severity_score"),
            )
            .order_by("plant__name")
        )

    @staticmethod
    def monthly_trend():
        return (
            Submission.objects
            .filter(workflow_state="SUBMITTED")
            .annotate(month=TruncMonth("submitted_at"))
            .values("month")
            .annotate(
                total=Count("pk"),
                avg_severity=Avg("severity_score"),
            )
            .order_by("month")
        )
