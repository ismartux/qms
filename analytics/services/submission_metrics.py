from django.db.models import Count, Avg, Q
from django.db.models.functions import TruncDate

from analytics.selectors.submission_selector import (
    submissions_qs,
    nc_responses_qs,
)


class SubmissionMetrics:

    @staticmethod
    def kpis(plant=None):
        qs = submissions_qs(plant=plant)

        return qs.aggregate(
            total=Count("submission_id"),
            avg_severity=Avg("severity_score"),
            high_severity=Count(
                "id",
                filter=Q(severity_score__gte=8)
            )
        )

    @staticmethod
    def severity_distribution(plant=None):
        return (
            submissions_qs(plant)
            .values("severity_score")
            .annotate(count=Count("submission_id"))
            .order_by("severity_score")
        )

    @staticmethod
    def severity_trend(plant=None):
        return (
            submissions_qs(plant)
            .annotate(day=TruncDate("submitted_at"))
            .values("day")
            .annotate(avg_severity=Avg("severity_score"))
            .order_by("day")
        )

    @staticmethod
    def template_comparison(plant=None):
        return (
            submissions_qs(plant)
            .values("template_version__template__code")
            .annotate(
                avg=Avg("severity_score"),
                total=Count("submission_id")
            )
            .order_by("-avg")
        )

    # 🔥 FIXED PARETO — SHOW ITEM LABEL
    @staticmethod
    def pareto_nc(plant=None, template=None, limit=10):
        return (
            nc_responses_qs(plant=plant, template=template)
            .values("item__label")  # requires FK to ChecklistItem
            .annotate(count=Count("submission_id"))
            .order_by("-count")[:limit]
        )
