"""
CAPA Analytics Engine for Quality Management System.
Aggregates and computes operational metrics, breakdowns, SLA aging,
and drill-down records for Corrective and Preventive Actions (CAPA).
"""

from datetime import datetime, time, timedelta
from django.utils import timezone
from django.db.models import (
    Count,
    Avg,
    Q,
    Case,
    When,
    Value,
    IntegerField,
    F,
)
from capa.models import CAPA
from org.models import Plant, Shop, Line, Product


class CapaAnalyticsService:
    """Service class for all CAPA dashboard aggregations, SLA tracking, and drill-downs."""

    @staticmethod
    def normalize_brand(brand_raw):
        """Normalizes inconsistent brand naming variations into clean display brands."""
        if not brand_raw:
            return "Unbranded"
        b = str(brand_raw).strip()
        b_upper = b.upper()
        if "NOTHING" in b_upper:
            return "Nothing"
        elif "INFINIX" in b_upper:
            return "Infinix"
        elif "TECNO" in b_upper or "TECHNO" in b_upper:
            return "Tecno"
        elif "NOVA" in b_upper or "AI+" in b_upper:
            return "AI+ Nova"
        elif "VILLAON" in b_upper:
            return "Villaon"
        return b.title()

    @staticmethod
    def resolve_date_range(range_key="today"):
        """Resolves period string into start and end datetimes (inclusive)."""
        now = timezone.now()
        today = now.date()

        if range_key == "today":
            start_dt = timezone.make_aware(datetime.combine(today, time.min))
            end_dt = timezone.make_aware(datetime.combine(today, time.max))
        elif range_key == "yesterday":
            yday = today - timedelta(days=1)
            start_dt = timezone.make_aware(datetime.combine(yday, time.min))
            end_dt = timezone.make_aware(datetime.combine(yday, time.max))
        elif range_key == "this_week":
            start_of_week = today - timedelta(days=today.weekday())
            start_dt = timezone.make_aware(datetime.combine(start_of_week, time.min))
            end_dt = timezone.make_aware(datetime.combine(today, time.max))
        elif range_key == "last_week":
            start_of_last_week = today - timedelta(days=today.weekday() + 7)
            end_of_last_week = start_of_last_week + timedelta(days=6)
            start_dt = timezone.make_aware(datetime.combine(start_of_last_week, time.min))
            end_dt = timezone.make_aware(datetime.combine(end_of_last_week, time.max))
        elif range_key == "this_month":
            start_of_month = today.replace(day=1)
            start_dt = timezone.make_aware(datetime.combine(start_of_month, time.min))
            end_dt = timezone.make_aware(datetime.combine(today, time.max))
        elif range_key == "all":
            return None, None
        else:
            start_dt = timezone.make_aware(datetime.combine(today, time.min))
            end_dt = timezone.make_aware(datetime.combine(today, time.max))

        return start_dt, end_dt

    @classmethod
    def get_reference_date(cls, range_key="all"):
        today = timezone.now().date()
        if range_key == "yesterday":
            return today - timedelta(days=1)
        elif range_key == "last_week":
            _, end_dt = cls.resolve_date_range("last_week")
            return end_dt.date() if end_dt else (today - timedelta(days=7))
        else:
            return today

    @classmethod
    def apply_filters(
        cls,
        qs,
        range_key="today",
        plant_id=None,
        shop_id=None,
        brand=None,
        line_id=None,
        status=None,
        severity=None,
    ):
        """Applies dimensional filters to a CAPA queryset."""
        start_dt, end_dt = cls.resolve_date_range(range_key)
        if start_dt and end_dt:
            qs = qs.filter(created_at__gte=start_dt, created_at__lte=end_dt)

        if plant_id:
            qs = qs.filter(
                Q(submission__work_context__plant_id=plant_id) |
                Q(submission__plant_id=plant_id)
            )

        if shop_id:
            qs = qs.filter(
                Q(submission__work_context__shop_id=shop_id) |
                Q(submission__shop_id=shop_id)
            )

        if brand:
            brand_clean = brand.strip().lower()
            qs = qs.filter(
                Q(submission__work_context__product__brand__icontains=brand_clean) |
                Q(submission__product__brand__icontains=brand_clean)
            )

        if line_id:
            qs = qs.filter(
                Q(submission__work_context__line_id=line_id) |
                Q(submission__line_id=line_id)
            )

        today = timezone.now().date()
        if status:
            status_upper = status.upper().strip()
            if status_upper == "OVERDUE":
                qs = qs.filter(due_date__lt=today).exclude(status="CLOSED")
            elif status_upper in ["OPEN", "ASSIGNED", "ACTION_DONE", "REJECTED", "CLOSED"]:
                qs = qs.filter(status=status_upper)

        if severity:
            sev_str = str(severity).strip().lower()
            if sev_str == "high":
                qs = qs.filter(severity__gte=7)
            elif sev_str == "medium":
                qs = qs.filter(severity__gte=4, severity__lte=6)
            elif sev_str == "low":
                qs = qs.filter(severity__lte=3)
            elif sev_str.isdigit():
                qs = qs.filter(severity=int(sev_str))

        return qs

    @classmethod
    def compute_summary_kpis(cls, qs, base_qs=None, range_key="all"):
        """Computes top-level executive summary KPIs for the filtered CAPA queryset."""
        ref_date = cls.get_reference_date(range_key)
        today = timezone.now().date()

        agg = qs.aggregate(
            total=Count("capa_id"),
            open_count=Count("capa_id", filter=Q(status="OPEN")),
            assigned_count=Count("capa_id", filter=Q(status="ASSIGNED")),
            action_done_count=Count("capa_id", filter=Q(status="ACTION_DONE")),
            rejected_count=Count("capa_id", filter=Q(status="REJECTED")),
            closed_count=Count("capa_id", filter=Q(status="CLOSED")),
            high_sev_count=Count("capa_id", filter=Q(severity__gte=7)),
            med_sev_count=Count("capa_id", filter=Q(severity__gte=4, severity__lte=6)),
            low_sev_count=Count("capa_id", filter=Q(severity__lte=3)),
            avg_severity=Avg("severity"),
        )

        # Overdue source: base_qs has all dimensional filters (plant, shop, brand, line, severity) applied,
        # but is not restricted by created_at, so active overdue CAPAs accurately populate across all time tabs!
        overdue_source_qs = base_qs if base_qs is not None else qs
        if range_key in ["yesterday", "last_week"]:
            overdue_source_qs = overdue_source_qs.filter(created_at__date__lte=ref_date)

        overdue_agg = overdue_source_qs.aggregate(
            overdue_count=Count("capa_id", filter=Q(due_date__lt=ref_date) & ~Q(status="CLOSED")),
            overdue_1d=Count("capa_id", filter=Q(due_date__lte=ref_date - timedelta(days=1)) & ~Q(status="CLOSED")),
            overdue_3d=Count("capa_id", filter=Q(due_date__lte=ref_date - timedelta(days=3)) & ~Q(status="CLOSED")),
            overdue_5d=Count("capa_id", filter=Q(due_date__lte=ref_date - timedelta(days=5)) & ~Q(status="CLOSED")),
            overdue_7d=Count("capa_id", filter=Q(due_date__lte=ref_date - timedelta(days=7)) & ~Q(status="CLOSED")),
        )

        total = agg["total"] or 0
        closed = agg["closed_count"] or 0
        overdue = overdue_agg["overdue_count"] or 0

        closure_rate = round((closed / total * 100), 1) if total > 0 else 0.0
        overdue_rate = round((overdue / total * 100), 1) if total > 0 else 0.0
        avg_sev = round(float(agg["avg_severity"] or 0), 2)

        return {
            "total": total,
            "open": agg["open_count"] or 0,
            "assigned": agg["assigned_count"] or 0,
            "action_done": agg["action_done_count"] or 0,
            "rejected": agg["rejected_count"] or 0,
            "closed": closed,
            "overdue": overdue,
            "overdue_1d": overdue_agg["overdue_1d"] or 0,
            "overdue_3d": overdue_agg["overdue_3d"] or 0,
            "overdue_5d": overdue_agg["overdue_5d"] or 0,
            "overdue_7d": overdue_agg["overdue_7d"] or 0,
            "high_severity": agg["high_sev_count"] or 0,
            "med_severity": agg["med_sev_count"] or 0,
            "low_severity": agg["low_sev_count"] or 0,
            "closure_rate": closure_rate,
            "overdue_rate": overdue_rate,
            "avg_severity": avg_sev,
        }

    @classmethod
    def get_plant_breakdown(cls, qs):
        """Computes plant-wise CAPA distribution and resolution metrics."""
        today = timezone.now().date()
        raw = qs.values(
            plant_id=F("submission__work_context__plant__id"),
            plant_name=F("submission__work_context__plant__name"),
            plant_code=F("submission__work_context__plant__code"),
        ).annotate(
            total=Count("capa_id"),
            open_count=Count("capa_id", filter=Q(status="OPEN")),
            assigned_count=Count("capa_id", filter=Q(status="ASSIGNED")),
            action_done_count=Count("capa_id", filter=Q(status="ACTION_DONE")),
            closed_count=Count("capa_id", filter=Q(status="CLOSED")),
            overdue_count=Count("capa_id", filter=Q(due_date__lt=today) & ~Q(status="CLOSED")),
            avg_sev=Avg("severity"),
        ).order_by("-total")

        results = []
        for r in raw:
            tot = r["total"] or 0
            cls_count = r["closed_count"] or 0
            p_name = r["plant_name"] or "Default / Central Plant"
            results.append({
                "plant_id": r["plant_id"],
                "plant_name": p_name,
                "plant_code": r["plant_code"] or "PLT",
                "total": tot,
                "open": r["open_count"] or 0,
                "assigned": r["assigned_count"] or 0,
                "action_done": r["action_done_count"] or 0,
                "closed": cls_count,
                "overdue": r["overdue_count"] or 0,
                "closure_rate": round((cls_count / tot * 100), 1) if tot > 0 else 0.0,
                "avg_severity": round(float(r["avg_sev"] or 0), 2),
            })
        return results

    @classmethod
    def get_section_breakdown(cls, qs):
        """Computes section / shop-wise CAPA metrics."""
        today = timezone.now().date()
        raw = qs.values(
            shop_id=F("submission__work_context__shop__id"),
            shop_name=F("submission__work_context__shop__name"),
            plant_name=F("submission__work_context__plant__name"),
        ).annotate(
            total=Count("capa_id"),
            open_count=Count("capa_id", filter=Q(status="OPEN")),
            assigned_count=Count("capa_id", filter=Q(status="ASSIGNED")),
            action_done_count=Count("capa_id", filter=Q(status="ACTION_DONE")),
            closed_count=Count("capa_id", filter=Q(status="CLOSED")),
            overdue_count=Count("capa_id", filter=Q(due_date__lt=today) & ~Q(status="CLOSED")),
            avg_sev=Avg("severity"),
        ).order_by("-total")

        results = []
        for r in raw:
            tot = r["total"] or 0
            cls_count = r["closed_count"] or 0
            results.append({
                "shop_id": r["shop_id"],
                "shop_name": r["shop_name"] or "General / Unassigned",
                "plant_name": r["plant_name"] or "Central",
                "total": tot,
                "open": r["open_count"] or 0,
                "assigned": r["assigned_count"] or 0,
                "action_done": r["action_done_count"] or 0,
                "closed": cls_count,
                "overdue": r["overdue_count"] or 0,
                "closure_rate": round((cls_count / tot * 100), 1) if tot > 0 else 0.0,
                "avg_severity": round(float(r["avg_sev"] or 0), 2),
            })
        return results

    @classmethod
    def get_brand_breakdown(cls, qs):
        """Computes brand-wise CAPA metrics with normalized brand grouping."""
        today = timezone.now().date()
        raw = qs.values(
            raw_brand=F("submission__work_context__product__brand"),
        ).annotate(
            total=Count("capa_id"),
            open_count=Count("capa_id", filter=Q(status="OPEN")),
            assigned_count=Count("capa_id", filter=Q(status="ASSIGNED")),
            action_done_count=Count("capa_id", filter=Q(status="ACTION_DONE")),
            closed_count=Count("capa_id", filter=Q(status="CLOSED")),
            overdue_count=Count("capa_id", filter=Q(due_date__lt=today) & ~Q(status="CLOSED")),
            avg_sev=Avg("severity"),
        )

        brand_map = {}
        for r in raw:
            norm = cls.normalize_brand(r["raw_brand"])
            if norm not in brand_map:
                brand_map[norm] = {
                    "brand": norm,
                    "total": 0,
                    "open": 0,
                    "assigned": 0,
                    "action_done": 0,
                    "closed": 0,
                    "overdue": 0,
                    "sev_sum": 0.0,
                    "sev_count": 0,
                }
            tot = r["total"] or 0
            brand_map[norm]["total"] += tot
            brand_map[norm]["open"] += r["open_count"] or 0
            brand_map[norm]["assigned"] += r["assigned_count"] or 0
            brand_map[norm]["action_done"] += r["action_done_count"] or 0
            brand_map[norm]["closed"] += r["closed_count"] or 0
            brand_map[norm]["overdue"] += r["overdue_count"] or 0
            if r["avg_sev"]:
                brand_map[norm]["sev_sum"] += float(r["avg_sev"]) * tot
                brand_map[norm]["sev_count"] += tot

        results = []
        for b, data in brand_map.items():
            tot = data["total"]
            cls_count = data["closed"]
            avg_s = round(data["sev_sum"] / data["sev_count"], 2) if data["sev_count"] > 0 else 0.0
            results.append({
                "brand": b,
                "total": tot,
                "open": data["open"],
                "assigned": data["assigned"],
                "action_done": data["action_done"],
                "closed": cls_count,
                "overdue": data["overdue"],
                "closure_rate": round((cls_count / tot * 100), 1) if tot > 0 else 0.0,
                "avg_severity": avg_s,
            })
        results.sort(key=lambda x: x["total"], reverse=True)
        return results

    @classmethod
    def get_line_breakdown(cls, qs):
        """Computes line-wise CAPA distribution and defect density."""
        today = timezone.now().date()
        raw = qs.values(
            line_id=F("submission__work_context__line__id"),
            line_name=F("submission__work_context__line__name"),
            shop_name=F("submission__work_context__shop__name"),
        ).annotate(
            total=Count("capa_id"),
            open_count=Count("capa_id", filter=Q(status="OPEN")),
            assigned_count=Count("capa_id", filter=Q(status="ASSIGNED")),
            action_done_count=Count("capa_id", filter=Q(status="ACTION_DONE")),
            closed_count=Count("capa_id", filter=Q(status="CLOSED")),
            overdue_count=Count("capa_id", filter=Q(due_date__lt=today) & ~Q(status="CLOSED")),
            avg_sev=Avg("severity"),
        ).order_by("-total")

        results = []
        for r in raw:
            tot = r["total"] or 0
            cls_count = r["closed_count"] or 0
            results.append({
                "line_id": r["line_id"],
                "line_name": r["line_name"] or "Common / Offline",
                "shop_name": r["shop_name"] or "General",
                "total": tot,
                "open": r["open_count"] or 0,
                "assigned": r["assigned_count"] or 0,
                "action_done": r["action_done_count"] or 0,
                "closed": cls_count,
                "overdue": r["overdue_count"] or 0,
                "closure_rate": round((cls_count / tot * 100), 1) if tot > 0 else 0.0,
                "avg_severity": round(float(r["avg_sev"] or 0), 2),
            })
        return results

    @classmethod
    def get_sla_aging_breakdown(cls, qs, base_qs=None, range_key="all"):
        """Computes SLA aging buckets for all active non-closed CAPAs."""
        ref_date = cls.get_reference_date(range_key)
        source_qs = base_qs if base_qs is not None else qs
        if range_key in ["yesterday", "last_week"]:
            source_qs = source_qs.filter(created_at__date__lte=ref_date)

        active_qs = source_qs.exclude(status="CLOSED")

        overdue_critical = active_qs.filter(due_date__lt=ref_date - timedelta(days=7)).count()
        overdue_warning = active_qs.filter(due_date__lt=ref_date, due_date__gte=ref_date - timedelta(days=7)).count()
        due_this_week = active_qs.filter(due_date__gte=ref_date, due_date__lte=ref_date + timedelta(days=7)).count()
        due_later = active_qs.filter(due_date__gt=ref_date + timedelta(days=7)).count()
        closed_count = qs.filter(status="CLOSED").count()

        return [
            {
                "bucket_key": "overdue_critical",
                "label": "Severely Overdue (> 7 Days)",
                "count": overdue_critical,
                "severity_tier": "Critical",
                "badge_class": "bg-rose-100 text-rose-800 border-rose-200",
                "icon": "fa-circle-exclamation",
                "color": "rose",
            },
            {
                "bucket_key": "overdue_warning",
                "label": "Overdue (1 - 7 Days)",
                "count": overdue_warning,
                "severity_tier": "High",
                "badge_class": "bg-red-100 text-red-800 border-red-200",
                "icon": "fa-triangle-exclamation",
                "color": "red",
            },
            {
                "bucket_key": "due_this_week",
                "label": "Due Within 7 Days",
                "count": due_this_week,
                "severity_tier": "Warning",
                "badge_class": "bg-amber-100 text-amber-800 border-amber-200",
                "icon": "fa-clock",
                "color": "amber",
            },
            {
                "bucket_key": "due_later",
                "label": "Due Later (> 7 Days)",
                "count": due_later,
                "severity_tier": "Normal",
                "badge_class": "bg-sky-100 text-sky-800 border-sky-200",
                "icon": "fa-calendar-check",
                "color": "sky",
            },
            {
                "bucket_key": "closed_resolved",
                "label": "Resolved & Closed",
                "count": closed_count,
                "severity_tier": "Done",
                "badge_class": "bg-emerald-100 text-emerald-800 border-emerald-200",
                "icon": "fa-circle-check",
                "color": "emerald",
            },
        ]

    @classmethod
    def get_severity_distribution(cls, qs):
        """Computes severity level distribution (Low: 1-3, Medium: 4-6, High: 7-10)."""
        today = timezone.now().date()
        low = qs.filter(severity__lte=3)
        med = qs.filter(severity__gte=4, severity__lte=6)
        high = qs.filter(severity__gte=7)

        def build_tier(name, tier_qs, color, badge_class, icon):
            tot = tier_qs.count()
            cls_count = tier_qs.filter(status="CLOSED").count()
            od_count = tier_qs.filter(due_date__lt=today).exclude(status="CLOSED").count()
            return {
                "name": name,
                "total": tot,
                "open": tier_qs.filter(status="OPEN").count(),
                "assigned": tier_qs.filter(status="ASSIGNED").count(),
                "action_done": tier_qs.filter(status="ACTION_DONE").count(),
                "closed": cls_count,
                "overdue": od_count,
                "closure_rate": round((cls_count / tot * 100), 1) if tot > 0 else 0.0,
                "color": color,
                "badge_class": badge_class,
                "icon": icon,
            }

        return [
            build_tier("High / Critical (Sev 7-10)", high, "rose", "bg-rose-100 text-rose-800 border-rose-300", "fa-fire"),
            build_tier("Medium (Sev 4-6)", med, "amber", "bg-amber-100 text-amber-800 border-amber-300", "fa-triangle-exclamation"),
            build_tier("Low (Sev 1-3)", low, "emerald", "bg-emerald-100 text-emerald-800 border-emerald-300", "fa-shield-halved"),
        ]

    @classmethod
    def get_role_assignment_breakdown(cls, qs):
        """Computes RCA and Action Role distribution (e.g. PE, PD, PQE, Production)."""
        today = timezone.now().date()
        raw = qs.values(
            role_id=F("rca_role__id"),
            role_name=F("rca_role__name"),
        ).annotate(
            total=Count("capa_id"),
            open_count=Count("capa_id", filter=Q(status="OPEN")),
            assigned_count=Count("capa_id", filter=Q(status="ASSIGNED")),
            action_done_count=Count("capa_id", filter=Q(status="ACTION_DONE")),
            closed_count=Count("capa_id", filter=Q(status="CLOSED")),
            overdue_count=Count("capa_id", filter=Q(due_date__lt=today) & ~Q(status="CLOSED")),
            avg_sev=Avg("severity"),
        ).order_by("-total")

        results = []
        for r in raw:
            tot = r["total"] or 0
            cls_count = r["closed_count"] or 0
            r_name = r["role_name"] or "Unassigned / Pending Routing"
            results.append({
                "role_id": r["role_id"],
                "role_name": r_name,
                "total": tot,
                "open": r["open_count"] or 0,
                "assigned": r["assigned_count"] or 0,
                "action_done": r["action_done_count"] or 0,
                "closed": cls_count,
                "overdue": r["overdue_count"] or 0,
                "closure_rate": round((cls_count / tot * 100), 1) if tot > 0 else 0.0,
                "avg_severity": round(float(r["avg_sev"] or 0), 2),
            })
        return results

    @classmethod
    def get_recent_capas(cls, qs, limit=20):
        """Fetches latest recent CAPAs with enriched relationships."""
        today = timezone.now().date()
        recent = qs.select_related(
            "submission",
            "submission__work_context__plant",
            "submission__work_context__shop",
            "submission__work_context__line",
            "submission__work_context__product",
            "submission__template_version__template",
            "rca_role",
            "capa_role",
        ).order_by("-created_at")[:limit]

        results = []
        for c in recent:
            wc = getattr(c.submission, "work_context", None)
            plant_name = getattr(wc.plant, "name", "—") if wc and wc.plant else "—"
            shop_name = getattr(wc.shop, "name", "—") if wc and wc.shop else "—"
            line_name = getattr(wc.line, "name", "—") if wc and wc.line else "—"
            product_name = getattr(wc.product, "name", "—") if wc and wc.product else "—"
            raw_brand = getattr(wc.product, "brand", None) if wc and wc.product else None
            brand = cls.normalize_brand(raw_brand)

            is_od = c.status != "CLOSED" and c.due_date and c.due_date < today
            days_overdue = (today - c.due_date).days if is_od else 0

            results.append({
                "capa_id": str(c.capa_id),
                "title": c.title,
                "template_name": getattr(c.submission.template_version.template, "name", "Inspection"),
                "plant_name": plant_name,
                "shop_name": shop_name,
                "line_name": line_name,
                "product_name": product_name,
                "brand": brand,
                "severity": c.severity,
                "status": c.status,
                "rca_role_name": c.rca_role.name if c.rca_role else "Unassigned",
                "capa_role_name": c.capa_role.name if c.capa_role else "Unassigned",
                "due_date": c.due_date.strftime("%d %b %Y") if c.due_date else "—",
                "is_overdue": is_od,
                "days_overdue": days_overdue,
                "created_at_str": c.created_at.strftime("%d %b %Y, %H:%M") if c.created_at else "—",
            })
        return results

    @classmethod
    def get_filter_options(cls):
        """Fetches distinct filter options for plant, section, brand, and line dropdowns."""
        plants = list(Plant.objects.filter(is_active=True).values("id", "name", "code").order_by("name"))
        shops = list(Shop.objects.filter(is_active=True).values("id", "name", "plant__name").order_by("name"))
        lines = list(Line.objects.filter(is_active=True).values("id", "name", "shop__name").order_by("name"))

        raw_brands = (
            Product.objects.exclude(brand__isnull=True)
            .exclude(brand="")
            .values_list("brand", flat=True)
            .distinct()
        )
        norm_brands = sorted(list({cls.normalize_brand(b) for b in raw_brands if b}))

        return {
            "plants": plants,
            "shops": shops,
            "lines": lines,
            "brands": norm_brands,
        }

    @classmethod
    def get_drilldown_details(
        cls,
        metric="total",
        target_id=None,
        target_name=None,
        plant_id=None,
        shop_id=None,
        brand=None,
        line_id=None,
        status=None,
        severity=None,
        range_key="today",
        limit=500,
    ):
        """
        Fetches full CAPA records matching clicked card/row and applied filters for the popup modal.
        """
        today = timezone.now().date()
        qs = CAPA.objects.select_related(
            "submission",
            "submission__work_context__plant",
            "submission__work_context__shop",
            "submission__work_context__line",
            "submission__work_context__product",
            "submission__template_version__template",
            "rca_role",
            "capa_role",
        )

        ref_date = cls.get_reference_date(range_key)
        metric_clean = (metric or "total").lower().strip()
        is_overdue_metric = metric_clean in [
            "overdue", "overdue_1d", "overdue_3d", "overdue_5d", "overdue_7d"
        ] or (metric_clean == "sla" and target_name in ["overdue_critical", "overdue_warning"])

        # 1. Base applied filters
        # For overdue drilldowns, do NOT filter out records by created_at range
        effective_range = "all" if is_overdue_metric else range_key
        qs = cls.apply_filters(
            qs,
            range_key=effective_range,
            plant_id=plant_id,
            shop_id=shop_id,
            brand=brand,
            line_id=line_id,
            status=status,
            severity=severity,
        )

        if is_overdue_metric and range_key in ["yesterday", "last_week"]:
            qs = qs.filter(created_at__date__lte=ref_date)

        # 2. Card / Metric specific drilldowns
        if metric_clean == "open":
            qs = qs.filter(status="OPEN")
        elif metric_clean == "assigned":
            qs = qs.filter(status="ASSIGNED")
        elif metric_clean == "action_done":
            qs = qs.filter(status="ACTION_DONE")
        elif metric_clean == "rejected":
            qs = qs.filter(status="REJECTED")
        elif metric_clean == "closed":
            qs = qs.filter(status="CLOSED")
        elif metric_clean == "overdue":
            qs = qs.filter(due_date__lt=ref_date).exclude(status="CLOSED")
        elif metric_clean == "overdue_1d":
            qs = qs.filter(due_date__lte=ref_date - timedelta(days=1)).exclude(status="CLOSED")
        elif metric_clean == "overdue_3d":
            qs = qs.filter(due_date__lte=ref_date - timedelta(days=3)).exclude(status="CLOSED")
        elif metric_clean == "overdue_5d":
            qs = qs.filter(due_date__lte=ref_date - timedelta(days=5)).exclude(status="CLOSED")
        elif metric_clean == "overdue_7d":
            qs = qs.filter(due_date__lte=ref_date - timedelta(days=7)).exclude(status="CLOSED")
        elif metric_clean == "high_severity":
            qs = qs.filter(severity__gte=7)
        elif metric_clean == "med_severity":
            qs = qs.filter(severity__gte=4, severity__lte=6)
        elif metric_clean == "low_severity":
            qs = qs.filter(severity__lte=3)
        elif metric_clean == "plant" and target_id:
            qs = qs.filter(submission__work_context__plant_id=target_id)
        elif metric_clean == "section" and target_id:
            qs = qs.filter(submission__work_context__shop_id=target_id)
        elif metric_clean == "line" and target_id:
            qs = qs.filter(submission__work_context__line_id=target_id)
        elif metric_clean == "brand" and target_name:
            norm_target = target_name.strip().lower()
            qs = qs.filter(submission__work_context__product__brand__icontains=norm_target)
        elif metric_clean == "role":
            if target_id:
                qs = qs.filter(rca_role_id=target_id)
            elif target_name and "unassigned" in target_name.lower():
                qs = qs.filter(rca_role__isnull=True)
        elif metric_clean == "sla":
            if target_name == "overdue_critical":
                qs = qs.filter(due_date__lt=ref_date - timedelta(days=7)).exclude(status="CLOSED")
            elif target_name == "overdue_warning":
                qs = qs.filter(due_date__lt=ref_date, due_date__gte=ref_date - timedelta(days=7)).exclude(status="CLOSED")
            elif target_name == "due_this_week":
                qs = qs.filter(due_date__gte=ref_date, due_date__lte=ref_date + timedelta(days=7)).exclude(status="CLOSED")
            elif target_name == "due_later":
                qs = qs.filter(due_date__gt=ref_date + timedelta(days=7)).exclude(status="CLOSED")
            elif target_name == "closed_resolved":
                qs = qs.filter(status="CLOSED")

        total_matching = qs.count()
        records = qs.order_by("-created_at")[:limit]

        data = []
        for c in records:
            wc = getattr(c.submission, "work_context", None)
            plant_name = getattr(wc.plant, "name", "—") if wc and wc.plant else "—"
            shop_name = getattr(wc.shop, "name", "—") if wc and wc.shop else "—"
            line_name = getattr(wc.line, "name", "—") if wc and wc.line else "—"
            product_name = getattr(wc.product, "name", "—") if wc and wc.product else "—"
            raw_brand = getattr(wc.product, "brand", None) if wc and wc.product else None
            brand_norm = cls.normalize_brand(raw_brand)

            is_od = c.status != "CLOSED" and c.due_date and c.due_date < ref_date
            days_od = (ref_date - c.due_date).days if is_od else 0

            data.append({
                "capa_id": str(c.capa_id),
                "title": c.title,
                "template_name": getattr(c.submission.template_version.template, "name", "Inspection"),
                "plant_name": plant_name,
                "shop_name": shop_name,
                "line_name": line_name,
                "product_name": product_name,
                "brand": brand_norm,
                "severity": c.severity,
                "status": c.status,
                "rca_role_name": c.rca_role.name if c.rca_role else "Unassigned",
                "capa_role_name": c.capa_role.name if c.capa_role else "Unassigned",
                "due_date_str": c.due_date.strftime("%d %b %Y") if c.due_date else "—",
                "is_overdue": is_od,
                "days_overdue": days_od,
                "created_at_str": c.created_at.strftime("%d %b %Y, %H:%M") if c.created_at else "—",
                "detail_url": f"/capa/{c.capa_id}/",
                "work_url": f"/capa/{c.capa_id}/work/",
            })

        return {
            "count": total_matching,
            "records": data,
        }
