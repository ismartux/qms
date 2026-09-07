# analytics/services/dashboard_analytics.py

from datetime import datetime, time, timedelta
from django.utils import timezone
from django.db.models import Count, Q, Avg, F
from submissions.models import Submission, SubmissionApproval, WorkContext
from org.models import Plant, Shop, Line, Product, FloorTLAssignment
from core.workflow.states import WorkflowState


class DashboardAnalyticsService:
    """
    Centralized analytics engine computing multi-dimensional performance
    metrics for Plant, Section, Brand, Line, IPQC, PQE, and TL operations.
    """

    VALID_STATES = [
        WorkflowState.SUBMITTED,
        WorkflowState.SYNC_PENDING,
        WorkflowState.SYNCED,
        WorkflowState.FAILED,
        WorkflowState.CLOSED,
    ]

    @staticmethod
    def resolve_date_range(range_key="today"):
        """
        Converts range key to (start_date, end_date) datetimes.
        """
        now = timezone.localtime()
        today_start = timezone.make_aware(datetime.combine(now.date(), time.min))
        today_end = timezone.make_aware(datetime.combine(now.date(), time.max))

        if range_key == "today":
            return today_start, now

        elif range_key == "yesterday":
            yesterday_date = now.date() - timedelta(days=1)
            start = timezone.make_aware(datetime.combine(yesterday_date, time.min))
            end = timezone.make_aware(datetime.combine(yesterday_date, time.max))
            return start, end

        elif range_key == "this_week":
            start_of_week = today_start - timedelta(days=now.weekday())
            return start_of_week, now

        elif range_key == "last_week":
            start_of_this_week = today_start - timedelta(days=now.weekday())
            start_of_last_week = start_of_this_week - timedelta(days=7)
            end_of_last_week = start_of_this_week - timedelta(microseconds=1)
            return start_of_last_week, end_of_last_week

        elif range_key == "this_month":
            start_of_month = timezone.make_aware(datetime(now.year, now.month, 1, 0, 0, 0))
            return start_of_month, now

        elif range_key == "all":
            return None, None

        return today_start, now

    @classmethod
    def get_base_queryset(cls, plant=None):
        qs = Submission.objects.filter(workflow_state__in=cls.VALID_STATES)
        if plant:
            qs = qs.filter(plant=plant)
        return qs

    @classmethod
    def apply_filters(cls, qs, plant_id=None, shop_id=None, brand=None, line_id=None, start_date=None, end_date=None):
        if plant_id:
            qs = qs.filter(plant_id=plant_id)
        if shop_id:
            qs = qs.filter(shop_id=shop_id)
        if brand:
            qs = qs.filter(product__brand__iexact=brand.strip())
        if line_id:
            qs = qs.filter(line_id=line_id)
        if start_date:
            qs = qs.filter(submitted_at__gte=start_date)
        if end_date:
            qs = qs.filter(submitted_at__lte=end_date)
        return qs

    @classmethod
    def compute_summary_kpis(cls, qs):
        """
        Calculates executive KPIs for the filtered submission set.
        """
        agg = qs.aggregate(
            total=Count("submission_id"),
            approved=Count("submission_id", filter=Q(approvals__status="APPROVED", approvals__category__code="PQE")),
            rejected=Count("submission_id", filter=Q(approvals__status="REJECTED", approvals__category__code="PQE")),
            avg_severity=Avg("severity_score"),
            high_severity=Count("submission_id", filter=Q(severity_score__gte=8)),
            active_lines=Count("line_id", distinct=True),
            active_brands=Count("product__brand", distinct=True),
            active_inspectors=Count("submitted_by_id", distinct=True),
        )

        total = agg.get("total") or 0
        approved = agg.get("approved") or 0
        rejected = agg.get("rejected") or 0
        decided = approved + rejected
        pending = max(0, total - decided)

        approval_rate = round((approved / total * 100), 1) if total > 0 else 0.0
        rejection_rate = round((rejected / total * 100), 1) if total > 0 else 0.0

        return {
            "total": total,
            "approved": approved,
            "rejected": rejected,
            "pending": pending,
            "approval_rate": approval_rate,
            "rejection_rate": rejection_rate,
            "avg_severity": round(agg.get("avg_severity") or 0.0, 2),
            "high_severity": agg.get("high_severity") or 0,
            "active_lines": agg.get("active_lines") or 0,
            "active_brands": agg.get("active_brands") or 0,
            "active_inspectors": agg.get("active_inspectors") or 0,
        }

    @classmethod
    def get_plant_breakdown(cls, qs):
        """
        Plant-wise submissions, approvals, rejections, approval %.
        """
        raw = (
            qs.exclude(plant__isnull=True)
            .values("plant__id", "plant__name", "plant__code")
            .annotate(
                total=Count("submission_id"),
                approved=Count("submission_id", filter=Q(approvals__status="APPROVED", approvals__category__code="PQE")),
                rejected=Count("submission_id", filter=Q(approvals__status="REJECTED", approvals__category__code="PQE")),
                avg_sev=Avg("severity_score"),
                lines_count=Count("line_id", distinct=True),
            )
            .order_by("-total")
        )

        results = []
        for r in raw:
            total = r["total"]
            appr = r["approved"]
            rej = r["rejected"]
            decided = appr + rej
            pend = max(0, total - decided)
            rate = round((appr / total * 100), 1) if total > 0 else 0.0

            results.append({
                "id": r["plant__id"],
                "name": r["plant__name"],
                "code": r["plant__code"] or r["plant__name"],
                "total": total,
                "approved": appr,
                "rejected": rej,
                "pending": pend,
                "approval_rate": rate,
                "lines_count": r["lines_count"],
                "avg_severity": round(r["avg_sev"] or 0.0, 2),
            })
        return results

    @classmethod
    def get_section_breakdown(cls, qs):
        """
        Section/Shop-wise submissions, approvals, rejections.
        """
        raw = (
            qs.exclude(shop__isnull=True)
            .values("shop__id", "shop__name", "plant__name")
            .annotate(
                total=Count("submission_id"),
                approved=Count("submission_id", filter=Q(approvals__status="APPROVED", approvals__category__code="PQE")),
                rejected=Count("submission_id", filter=Q(approvals__status="REJECTED", approvals__category__code="PQE")),
                lines_count=Count("line_id", distinct=True),
            )
            .order_by("-total")
        )

        results = []
        for r in raw:
            total = r["total"]
            appr = r["approved"]
            rej = r["rejected"]
            decided = appr + rej
            pend = max(0, total - decided)
            rate = round((appr / total * 100), 1) if total > 0 else 0.0

            results.append({
                "id": r["shop__id"],
                "name": r["shop__name"],
                "plant_name": r["plant__name"],
                "total": total,
                "approved": appr,
                "rejected": rej,
                "pending": pend,
                "approval_rate": rate,
                "lines_count": r["lines_count"],
            })
        return results

    @classmethod
    def get_brand_breakdown(cls, qs):
        """
        Brand-wise submissions and approval rates, normalized.
        """
        raw = (
            qs.exclude(product__brand="")
            .exclude(product__brand__isnull=True)
            .values("product__brand")
            .annotate(
                total=Count("submission_id"),
                approved=Count("submission_id", filter=Q(approvals__status="APPROVED", approvals__category__code="PQE")),
                rejected=Count("submission_id", filter=Q(approvals__status="REJECTED", approvals__category__code="PQE")),
                models_count=Count("product_id", distinct=True),
            )
            .order_by("-total")
        )

        merged = {}
        for r in raw:
            brand_raw = r["product__brand"].strip()
            brand_norm = brand_raw.title()
            if brand_norm.lower() == "infinix":
                brand_norm = "Infinix"
            elif brand_norm.lower() in ["tecno", "techno"]:
                brand_norm = "Tecno"
            elif brand_norm.lower() == "nothing":
                brand_norm = "Nothing"
            elif brand_norm.lower().startswith("ai+"):
                brand_norm = "AI+ Nova"
            elif brand_norm.lower() == "villaon":
                brand_norm = "Villaon"

            if brand_norm not in merged:
                merged[brand_norm] = {
                    "brand": brand_norm,
                    "total": 0,
                    "approved": 0,
                    "rejected": 0,
                    "models_count": 0,
                }
            merged[brand_norm]["total"] += r["total"]
            merged[brand_norm]["approved"] += r["approved"]
            merged[brand_norm]["rejected"] += r["rejected"]
            merged[brand_norm]["models_count"] = max(merged[brand_norm]["models_count"], r["models_count"])

        results = []
        for b in sorted(merged.values(), key=lambda x: x["total"], reverse=True):
            total = b["total"]
            appr = b["approved"]
            rej = b["rejected"]
            decided = appr + rej
            pend = max(0, total - decided)
            rate = round((appr / total * 100), 1) if total > 0 else 0.0

            results.append({
                "brand": b["brand"],
                "total": total,
                "approved": appr,
                "rejected": rej,
                "pending": pend,
                "approval_rate": rate,
                "models_count": b["models_count"],
            })
        return results

    @classmethod
    def get_line_breakdown(cls, qs):
        """
        Line-wise submissions, shop name, approvals.
        """
        raw = (
            qs.exclude(line__isnull=True)
            .values("line__id", "line__name", "shop__name", "plant__name")
            .annotate(
                total=Count("submission_id"),
                approved=Count("submission_id", filter=Q(approvals__status="APPROVED", approvals__category__code="PQE")),
                rejected=Count("submission_id", filter=Q(approvals__status="REJECTED", approvals__category__code="PQE")),
                avg_sev=Avg("severity_score"),
            )
            .order_by("-total")
        )

        results = []
        for r in raw:
            total = r["total"]
            appr = r["approved"]
            rej = r["rejected"]
            decided = appr + rej
            pend = max(0, total - decided)
            rate = round((appr / total * 100), 1) if total > 0 else 0.0

            results.append({
                "id": r["line__id"],
                "name": r["line__name"],
                "shop_name": r["shop__name"] or "—",
                "plant_name": r["plant__name"] or "—",
                "total": total,
                "approved": appr,
                "rejected": rej,
                "pending": pend,
                "approval_rate": rate,
                "avg_severity": round(r["avg_sev"] or 0.0, 2),
            })
        return results

    @classmethod
    def get_ipqc_inspector_breakdown(cls, qs):
        """
        IPQC Inspector performance: inspections done, approval rate, defects.
        """
        raw = (
            qs.exclude(submitted_by__isnull=True)
            .values(
                "submitted_by__id",
                "submitted_by__username",
                "submitted_by__first_name",
                "submitted_by__last_name",
                "plant__name",
            )
            .annotate(
                total=Count("submission_id"),
                approved=Count("submission_id", filter=Q(approvals__status="APPROVED", approvals__category__code="PQE")),
                rejected=Count("submission_id", filter=Q(approvals__status="REJECTED", approvals__category__code="PQE")),
                avg_sev=Avg("severity_score"),
                lines_covered=Count("line_id", distinct=True),
            )
            .order_by("-total")
        )

        results = []
        for r in raw:
            total = r["total"]
            appr = r["approved"]
            rej = r["rejected"]
            decided = appr + rej
            pend = max(0, total - decided)
            rate = round((appr / total * 100), 1) if total > 0 else 0.0

            first = (r["submitted_by__first_name"] or "").strip()
            last = (r["submitted_by__last_name"] or "").strip()
            name = f"{first} {last}".strip() or r["submitted_by__username"]

            results.append({
                "user_id": r["submitted_by__id"],
                "username": r["submitted_by__username"],
                "name": name,
                "plant_name": r["plant__name"] or "—",
                "total": total,
                "approved": appr,
                "rejected": rej,
                "pending": pend,
                "approval_rate": rate,
                "lines_covered": r["lines_covered"],
                "avg_severity": round(r["avg_sev"] or 0.0, 2),
            })
        return results

    @classmethod
    def get_pqe_approver_breakdown(cls, qs):
        """
        PQE quality approval velocity: reviews done, approvals, rejections.
        """
        sub_ids = qs.values_list("submission_id", flat=True)

        raw = (
            SubmissionApproval.objects.filter(
                submission_id__in=sub_ids,
                category__code="PQE",
            )
            .exclude(approver_name="")
            .values("approver_name")
            .annotate(
                total=Count("id"),
                approved=Count("id", filter=Q(status="APPROVED")),
                rejected=Count("id", filter=Q(status="REJECTED")),
            )
            .order_by("-total")
        )

        results = []
        for r in raw:
            total = r["total"]
            appr = r["approved"]
            rej = r["rejected"]
            rate = round((appr / total * 100), 1) if total > 0 else 0.0
            rej_rate = round((rej / total * 100), 1) if total > 0 else 0.0

            results.append({
                "approver_name": r["approver_name"],
                "total": total,
                "approved": appr,
                "rejected": rej,
                "approval_rate": rate,
                "rejection_rate": rej_rate,
            })
        return results

    @classmethod
    def get_tl_floor_breakdown(cls, qs):
        """
        Team Leader floor assignments and performance under their line/floor supervision.
        """
        assignments = FloorTLAssignment.objects.select_related("floor", "user", "floor__plant").all()

        results = []
        for a in assignments:
            floor = a.floor
            tl_user = a.user
            first = (tl_user.first_name or "").strip()
            last = (tl_user.last_name or "").strip()
            tl_name = f"{first} {last}".strip() or tl_user.username

            floor_subs = qs.filter(floor=floor)
            total = floor_subs.count()
            appr = floor_subs.filter(approvals__status="APPROVED", approvals__category__code="PQE").count()
            rej = floor_subs.filter(approvals__status="REJECTED", approvals__category__code="PQE").count()
            decided = appr + rej
            pend = max(0, total - decided)
            rate = round((appr / total * 100), 1) if total > 0 else 0.0

            results.append({
                "tl_name": tl_name,
                "employee_id": tl_user.username,
                "floor_name": floor.name,
                "plant_name": floor.plant.name if floor.plant else "—",
                "shift": a.shift,
                "total": total,
                "approved": appr,
                "rejected": rej,
                "pending": pend,
                "approval_rate": rate,
            })
        return results

    @classmethod
    def get_filter_options(cls):
        """
        Dropdown values for multi-dimensional filters.
        """
        plants = list(Plant.objects.filter(is_active=True).values("id", "name", "code").order_by("name"))
        shops = list(Shop.objects.filter(is_active=True).values("id", "name", "plant__name").order_by("name"))
        lines = list(Line.objects.filter(is_active=True).values("id", "name", "shop__name").order_by("name"))

        brands_raw = (
            Product.objects.filter(is_active=True)
            .exclude(brand="")
            .exclude(brand__isnull=True)
            .values_list("brand", flat=True)
            .distinct()
        )

        brand_set = set()
        for b in brands_raw:
            norm = b.strip().title()
            if norm.lower() == "infinix":
                norm = "Infinix"
            elif norm.lower() in ["tecno", "techno"]:
                norm = "Tecno"
            elif norm.lower() == "nothing":
                norm = "Nothing"
            elif norm.lower().startswith("ai+"):
                norm = "AI+ Nova"
            elif norm.lower() == "villaon":
                norm = "Villaon"
            if norm:
                brand_set.add(norm)

        return {
            "plants": plants,
            "shops": shops,
            "lines": lines,
            "brands": sorted(list(brand_set)),
        }

    @classmethod
    def get_recent_submissions(cls, qs, limit=20):
        items = (
            qs.select_related(
                "template_version__template",
                "submitted_by",
                "plant",
                "shop",
                "line",
                "product",
            )
            .prefetch_related("approvals__category")
            .order_by("-submitted_at")[:limit]
        )

        results = []
        for s in items:
            pqe_approvals = [a for a in s.approvals.all() if a.category and a.category.code == "PQE"]
            if pqe_approvals:
                pqe_approvals.sort(key=lambda a: a.created_at or timezone.now(), reverse=True)
                latest_appr = pqe_approvals[0]
                pqe_status = latest_appr.status
                pqe_approver = latest_appr.approver_name
                rejection_reason = latest_appr.rejection_reason or ""
            else:
                pqe_status = "PENDING"
                pqe_approver = "—"
                rejection_reason = ""

            sub_user = s.submitted_by
            user_name = f"{sub_user.first_name} {sub_user.last_name}".strip() if sub_user else "—"
            if not user_name:
                user_name = sub_user.username if sub_user else "—"

            results.append({
                "submission_id": str(s.submission_id),
                "template_name": s.template_version.template.name if s.template_version else "Checklist",
                "plant_name": s.plant.name if s.plant else "—",
                "shop_name": s.shop.name if s.shop else "—",
                "line_name": s.line.name if s.line else "—",
                "product_name": s.product.name if s.product else "—",
                "brand": s.product.brand if (s.product and s.product.brand) else "—",
                "submitted_by_name": user_name,
                "submitted_by_username": sub_user.username if sub_user else "—",
                "submitted_at": s.submitted_at,
                "severity_score": s.severity_score,
                "pqe_status": pqe_status,
                "pqe_approver": pqe_approver,
                "rejection_reason": rejection_reason,
            })
        return results

    @classmethod
    def get_full_dashboard_data(cls, user=None, plant_id=None, shop_id=None, brand=None, line_id=None, range_key="today"):
        start_date, end_date = cls.resolve_date_range(range_key)
        base_qs = cls.get_base_queryset()
        filtered_qs = cls.apply_filters(
            base_qs,
            plant_id=plant_id,
            shop_id=shop_id,
            brand=brand,
            line_id=line_id,
            start_date=start_date,
            end_date=end_date,
        )

        kpis = cls.compute_summary_kpis(filtered_qs)
        plant_breakdown = cls.get_plant_breakdown(filtered_qs)
        section_breakdown = cls.get_section_breakdown(filtered_qs)
        brand_breakdown = cls.get_brand_breakdown(filtered_qs)
        line_breakdown = cls.get_line_breakdown(filtered_qs)
        ipqc_breakdown = cls.get_ipqc_inspector_breakdown(filtered_qs)
        pqe_breakdown = cls.get_pqe_approver_breakdown(filtered_qs)
        tl_breakdown = cls.get_tl_floor_breakdown(filtered_qs)
        recent_submissions = cls.get_recent_submissions(filtered_qs, limit=20)
        options = cls.get_filter_options()

        return {
            "kpis": kpis,
            "plant_breakdown": plant_breakdown,
            "section_breakdown": section_breakdown,
            "brand_breakdown": brand_breakdown,
            "line_breakdown": line_breakdown,
            "ipqc_breakdown": ipqc_breakdown,
            "pqe_breakdown": pqe_breakdown,
            "tl_breakdown": tl_breakdown,
            "recent_submissions": recent_submissions,
            "filter_options": options,
            "selected_range": range_key,
            "selected_plant_id": plant_id or "",
            "selected_shop_id": shop_id or "",
            "selected_brand": brand or "",
            "selected_line_id": line_id or "",
        }

    @classmethod
    def get_drilldown_details(cls, metric="total", target_id=None, target_name=None,
                               plant_id=None, shop_id=None, brand=None, line_id=None, range_key="today", limit=500):
        """
        Retrieves detailed submission records for popup drilldown when clicking on any KPI or dimension card.
        """
        start_date, end_date = cls.resolve_date_range(range_key)
        base_qs = cls.get_base_queryset()
        qs = cls.apply_filters(
            base_qs,
            plant_id=plant_id,
            shop_id=shop_id,
            brand=brand,
            line_id=line_id,
            start_date=start_date,
            end_date=end_date,
        )

        title = "Detailed Submissions"

        if metric == "total":
            title = "All Submissions"
        elif metric == "approved":
            qs = qs.filter(approvals__status="APPROVED", approvals__category__code="PQE")
            title = "PQE Approved Submissions"
        elif metric == "rejected":
            qs = qs.filter(approvals__status="REJECTED", approvals__category__code="PQE")
            title = "PQE Rejected Submissions"
        elif metric == "pending":
            qs = qs.exclude(approvals__status="APPROVED", approvals__category__code="PQE")
            qs = qs.exclude(approvals__status="REJECTED", approvals__category__code="PQE")
            title = "Pending PQE Review Submissions"
        elif metric == "plant" and target_id:
            qs = qs.filter(plant_id=target_id)
            plant_obj = Plant.objects.filter(id=target_id).first()
            title = f"Submissions for Plant: {plant_obj.name if plant_obj else target_id}"
        elif metric == "shop" and target_id:
            qs = qs.filter(shop_id=target_id)
            shop_obj = Shop.objects.filter(id=target_id).first()
            title = f"Submissions for Section: {shop_obj.name if shop_obj else target_id}"
        elif metric == "brand" and target_name:
            qs = qs.filter(product__brand__iexact=target_name.strip())
            title = f"Submissions for Brand: {target_name}"
        elif metric == "line" and target_id:
            qs = qs.filter(line_id=target_id)
            line_obj = Line.objects.filter(id=target_id).first()
            title = f"Submissions for Line: {line_obj.name if line_obj else target_id}"
        elif metric == "inspector":
            if target_id:
                qs = qs.filter(submitted_by_id=target_id)
            elif target_name:
                qs = qs.filter(submitted_by__username=target_name)
            title = f"Inspections by IPQC: {target_name or target_id}"
        elif metric == "pqe" and target_name:
            qs = qs.filter(approvals__approver_name=target_name, approvals__category__code="PQE")
            title = f"Quality Reviews by PQE: {target_name}"
        elif metric == "tl" and target_name:
            if str(target_name).isdigit():
                qs = qs.filter(floor_id=int(target_name))
            else:
                qs = qs.filter(floor__name__icontains=target_name)
            title = f"Submissions under TL Floor: {target_name}"

        total_count = qs.count()
        records = cls.get_recent_submissions(qs, limit=limit)

        return {
            "title": title,
            "count": total_count,
            "metric": metric,
            "records": records,
        }

