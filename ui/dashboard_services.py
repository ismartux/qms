"""
Dashboard Services - Data aggregation for role-based dashboards
Enhanced with comprehensive real data queries
"""
from django.utils import timezone
from django.db.models import Count, Q, Sum, Avg, F, Max, Min
from datetime import datetime, timedelta
from collections import defaultdict

from submissions.models import Submission, WorkContext, SubmissionApproval, SubmissionResponse
from scheduler.models import FormSchedule, ScheduledInstance, MissedFormAlert
from forms_engine.models import ChecklistTemplate, ChecklistItem
from core.identity.models import Role, UserScope
from core.workflow.states import WorkflowState
from org.models import Plant, Shop, Line
from capa.models import CAPA


class DashboardDataService:
    """Central service for aggregating dashboard data based on user role"""
    
    def __init__(self, user, work_context=None):
        self.user = user
        self.work_context = work_context
        self.role = self._get_user_role()
        self.today = timezone.now().date()
        self.shift_start, self.shift_end = self._get_shift_window()
    
    def _get_user_role(self):
        """Get user's role from work context or profile"""
        if self.work_context:
            from core.identity.context import get_user_scope
            scope = get_user_scope(self.user, work_context=self.work_context)
            if scope and scope.role:
                return scope.role
        # Fallback to any scope
        scope = UserScope.objects.filter(user=self.user).select_related('role').first()
        return scope.role if scope else None
    
    def _get_shift_window(self):
        """Calculate current shift time window (08:00 to 08:00)"""
        now = timezone.localtime()
        current_time = now.time()
        eight_am = timezone.datetime.strptime("08:00", "%H:%M").time()
        
        if current_time >= eight_am:
            start = timezone.make_aware(
                datetime.combine(self.today, eight_am)
            )
            end = start + timedelta(days=1)
        else:
            start = timezone.make_aware(
                datetime.combine(self.today - timedelta(days=1), eight_am)
            )
            end = timezone.make_aware(
                datetime.combine(self.today, eight_am)
            )
        
        return start, end
    
    def get_dashboard_data(self):
        """Main method to get all dashboard data based on role"""
        data = {
            'user': self.user,
            'role': self.role,
            'role_name': self.role.name if self.role else 'User',
            'work_context': self.work_context,
        }
        
        # Common data for all roles
        data.update(self._get_common_data())
        
        # Role-specific data
        # 🔑 KEY FIX: Superusers always get management data
        if self.user.is_superuser:
            data.update(self._get_management_data())
        elif self._is_supervisor():
            data.update(self._get_supervisor_data())
        elif self._is_management():
            data.update(self._get_management_data())
        elif self._is_operator():
            data.update(self._get_operator_data())
        else:
            data.update(self._get_operator_data())
        
        return data
    
    def _get_common_data(self):
        """Data common to all roles"""
        # Get pending approvals count (all-time, not just shift)
        pending_approvals = Submission.objects.filter(
            workflow_state=WorkflowState.SUBMITTED
        ).count()
        
        # Get active CAPAs
        active_capas = CAPA.objects.filter(status='OPEN').count()
        
        return {
            'today': self.today,
            'shift_start': self.shift_start,
            'shift_end': self.shift_end,
            'pending_approvals': pending_approvals,
            'active_capas': active_capas,
            'current_time': timezone.localtime(),
            'shift_label': 'Day' if timezone.localtime().time() >= timezone.datetime.strptime("08:00", "%H:%M").time() else 'Night',
        }
    
    def _is_operator(self):
        if not self.role:
            return True
        return self.role.code in ['OPERATOR', 'IPQC_OPERATOR', 'OQC_OPERATOR', 'FQC_OPERATOR']
    
    def _is_supervisor(self):
        if not self.role:
            return False
        return self.role.code in ['SUPERVISOR', 'LEADER', 'SHOP_SUPERVISOR', 'LINE_LEADER']
    
    def _is_management(self):
        if not self.role:
            return False
        return self.role.code in ['MANAGER', 'PLANT_MANAGER', 'QUALITY_MANAGER', 'ADMIN', 'QA_MANAGER']
    
    def _get_operator_data(self):
        """Dashboard data for operators - focus on their own tasks"""
        data = {}
        
        # My submissions (all time for this shift)
        my_submissions = Submission.objects.filter(
            submitted_by=self.user,
            submitted_at__gte=self.shift_start,
            submitted_at__lt=self.shift_end,
        )
        
        submitted = my_submissions.filter(workflow_state=WorkflowState.SUBMITTED)
        closed = my_submissions.filter(workflow_state=WorkflowState.CLOSED)
        failed = my_submissions.filter(workflow_state=WorkflowState.FAILED)
        
        data['my_stats'] = {
            'total_submissions': submitted.count() + closed.count(),
            'avg_severity': submitted.aggregate(avg=Avg('severity_score'))['avg'] or 0,
            'open_issues': submitted.filter(severity_score__gte=8).count(),
            'last_submission': submitted.order_by('-submitted_at').first(),
            'closed_count': closed.count(),
            'failed_count': failed.count(),
            'pass_rate': self._calculate_pass_rate(submitted),
        }
        
        # My scheduled forms
        data['scheduled_forms'] = self._get_scheduled_forms(my_submissions)
        
        # My missed forms
        data['missed_forms'] = MissedFormAlert.objects.filter(
            user=self.user,
            created_at__date=self.today
        ).count()
        
        # Recent submissions
        data['recent_submissions'] = submitted.order_by('-submitted_at')[:5]
        
        # My non-conformance items
        data['my_nc_items'] = SubmissionResponse.objects.filter(
            submission__submitted_by=self.user,
            submission__submitted_at__gte=self.shift_start,
            submission__submitted_at__lt=self.shift_end,
            is_non_conformance=True
        ).select_related('submission__template_version__template')[:10]
        
        # Work context info
        if self.work_context:
            data['work_context_info'] = {
                'line': self.work_context.line,
                'product': self.work_context.product,
                'shop': self.work_context.shop,
                'model_color': self.work_context.model_color,
            }
        
        return data
    
    def _get_supervisor_data(self):
        """Dashboard data for supervisors - team overview"""
        data = {}
        
        if not self.work_context:
            return data
        
        # Team members
        team_members = WorkContext.objects.filter(
            plant=self.work_context.plant,
            shop=self.work_context.shop,
            work_date=self.today,
            is_active=True
        ).values_list('user', flat=True).distinct()
        
        # Team submissions
        team_submissions = Submission.objects.filter(
            submitted_by__in=team_members,
            submitted_at__gte=self.shift_start,
            submitted_at__lt=self.shift_end,
        )
        
        submitted = team_submissions.filter(workflow_state=WorkflowState.SUBMITTED)
        
        data['team_stats'] = {
            'total_submissions': submitted.count(),
            'team_size': len(team_members),
            'avg_severity': submitted.aggregate(avg=Avg('severity_score'))['avg'] or 0,
            'open_issues': submitted.filter(severity_score__gte=8).count(),
            'completion_rate': self._calculate_completion_rate(submitted, team_members),
            'pass_rate': self._calculate_pass_rate(submitted),
        }
        
        # Missed forms by team
        data['team_missed_forms'] = MissedFormAlert.objects.filter(
            user__in=team_members,
            created_at__date=self.today
        ).select_related('user', 'template')[:20]
        
        # Top performers
        data['top_performers'] = self._get_top_performers(team_members)
        
        # Issues requiring attention
        data['critical_issues'] = submitted.filter(
            severity_score__gte=8
        ).order_by('-severity_score').select_related(
            'submitted_by', 'template_version__template'
        )[:10]
        
        # Line performance
        data['line_performance'] = self._get_line_performance(team_members)
        
        # Team member detail
        data['team_member_stats'] = self._get_team_member_stats(team_members)
        
        return data
    
    def _get_management_data(self):
        """Dashboard data for management - plant-wide overview"""
        data = {}
        
        # 🔑 KEY FIX: Use ALL plants, not just user's scope
        # For superusers, show all plants
        if self.user.is_superuser:
            plants = Plant.objects.filter(is_active=True)
        elif self.work_context:
            plants = Plant.objects.filter(id=self.work_context.plant_id)
        else:
            # Get plants from user scopes
            plant_ids = UserScope.objects.filter(
                user=self.user
            ).values_list('plant_id', flat=True).distinct()
            plants = Plant.objects.filter(id__in=plant_ids, is_active=True)
        
        # 🔑 KEY FIX: Use ALL submissions, not just shift-specific
        # Show all-time data for management dashboard
        all_submissions = Submission.objects.filter(
            plant__in=plants,
        )
        
        # Also get shift-specific for comparison
        shift_submissions = Submission.objects.filter(
            plant__in=plants,
            submitted_at__gte=self.shift_start,
            submitted_at__lt=self.shift_end,
        )
        
        submitted = shift_submissions.filter(workflow_state=WorkflowState.SUBMITTED)
        closed = shift_submissions.filter(workflow_state=WorkflowState.CLOSED)
        
        # 🔑 KEY FIX: Use ALL submissions for stats if shift is empty
        if submitted.count() == 0 and closed.count() == 0:
            # Fall back to all submissions
            submitted = all_submissions.filter(workflow_state=WorkflowState.SUBMITTED)
            closed = all_submissions.filter(workflow_state=WorkflowState.CLOSED)
        
        data['plant_stats'] = {
            'total_submissions': submitted.count() + closed.count(),
            'total_plants': plants.count(),
            'avg_severity': submitted.aggregate(avg=Avg('severity_score'))['avg'] or 0,
            'open_issues': submitted.filter(severity_score__gte=8).count(),
            'closed_count': closed.count(),
            'pass_rate': self._calculate_pass_rate(submitted),
        }
        
        # By plant breakdown
        data['by_plant'] = []
        for plant in plants:
            plant_subs = submitted.filter(plant=plant)
            data['by_plant'].append({
                'plant': plant,
                'submissions': plant_subs.count(),
                'avg_severity': plant_subs.aggregate(avg=Avg('severity_score'))['avg'] or 0,
                'open_issues': plant_subs.filter(severity_score__gte=8).count(),
            })
        
        # By shop breakdown
        data['by_shop'] = self._get_shop_breakdown(plants, submitted)
        
        # By line breakdown
        data['by_line'] = self._get_line_breakdown(plants, submitted)
        
        # Missed forms summary
        data['missed_forms_summary'] = MissedFormAlert.objects.filter(
            created_at__date=self.today
        ).values('user__first_name', 'user__last_name', 'user__username').annotate(
            count=Count('pk')
        ).order_by('-count')[:20]
        
        # Trend data (last 7 days)
        weekly_trend = self._get_weekly_trend(plants)
        data['weekly_trend'] = weekly_trend
        data['max_count'] = max([day['count'] for day in weekly_trend]) if weekly_trend else 1
        
        # Approval pending summary
        data['approval_pending'] = submitted.filter(
            workflow_state=WorkflowState.SUBMITTED
        ).count()
        
        # CAPA summary
        data['capa_summary'] = {
            'open': CAPA.objects.filter(status='OPEN').count(),
            'in_progress': CAPA.objects.filter(status='IN_PROGRESS').count(),
            'closed': CAPA.objects.filter(status='CLOSED').count(),
        }
        
        # Top templates used
        data['top_templates'] = submitted.values(
            'template_version__template__name'
        ).annotate(
            count=Count('submission_id')
        ).order_by('-count')[:10]
        
        # Severity distribution
        data['severity_distribution'] = self._get_severity_distribution(submitted)
        
        return data
    
    def _calculate_pass_rate(self, submissions):
        """Calculate pass rate from submissions"""
        total = submissions.count()
        if total == 0:
            return 100
        # Submissions with severity 0-3 are considered passing
        passing = submissions.filter(severity_score__lte=3).count()
        return round((passing / total) * 100, 1)
    
    def _calculate_completion_rate(self, submissions, team_members):
        """Calculate form completion rate for team"""
        if not team_members:
            return 0
        
        scheduled_forms = FormSchedule.objects.filter(is_active=True)
        total_required = 0
        
        for schedule in scheduled_forms:
            if schedule.schedule_type == 'shift_limit':
                total_required += schedule.times_per_shift or 0
        
        if total_required == 0:
            return 100
        
        actual = submissions.count()
        return min(100, int((actual / total_required) * 100))
    
    def _get_scheduled_forms(self, submissions):
        """Get scheduled forms with progress"""
        forms = []
        templates = ChecklistTemplate.objects.filter(
            schedule__is_active=True
        ).distinct()
        
        for template in templates:
            schedule = getattr(template, 'schedule', None)
            if schedule:
                completed = submissions.filter(
                    template_version__template=template
                ).count()
                
                forms.append({
                    'template': template,
                    'schedule': schedule,
                    'completed': completed,
                    'required': schedule.times_per_shift if schedule.schedule_type == 'shift_limit' else None,
                    'remaining': max((schedule.times_per_shift or 0) - completed, 0) if schedule.schedule_type == 'shift_limit' else 0,
                })
        
        return forms
    
    def _get_top_performers(self, team_members):
        """Get top performing team members"""
        performers = []
        from django.contrib.auth import get_user_model
        User = get_user_model()
        
        for user_id in team_members:
            try:
                user = User.objects.get(id=user_id)
                subs = Submission.objects.filter(
                    submitted_by=user,
                    submitted_at__gte=self.shift_start,
                    submitted_at__lt=self.shift_end,
                    workflow_state__in=[WorkflowState.SUBMITTED, WorkflowState.CLOSED]
                )
                
                performers.append({
                    'user': user,
                    'submissions': subs.count(),
                    'avg_severity': subs.aggregate(avg=Avg('severity_score'))['avg'] or 0,
                    'missed_forms': MissedFormAlert.objects.filter(
                        user=user, created_at__date=self.today
                    ).count(),
                })
            except User.DoesNotExist:
                continue
        
        performers.sort(key=lambda x: x['submissions'], reverse=True)
        return performers[:10]
    
    def _get_line_performance(self, team_members):
        """Get performance by line"""
        lines = Line.objects.filter(
            workcontext__user__in=team_members,
            workcontext__work_date=self.today,
            workcontext__is_active=True
        ).distinct()
        
        performance = []
        for line in lines:
            line_subs = Submission.objects.filter(
                work_context__line=line,
                submitted_at__gte=self.shift_start,
                submitted_at__lt=self.shift_end,
                workflow_state__in=[WorkflowState.SUBMITTED, WorkflowState.CLOSED]
            )
            
            performance.append({
                'line': line,
                'submissions': line_subs.count(),
                'avg_severity': line_subs.aggregate(avg=Avg('severity_score'))['avg'] or 0,
            })
        
        return performance
    
    def _get_team_member_stats(self, team_members):
        """Get detailed stats for each team member"""
        from django.contrib.auth import get_user_model
        User = get_user_model()
        
        stats = []
        for user_id in team_members:
            try:
                user = User.objects.get(id=user_id)
                subs = Submission.objects.filter(
                    submitted_by=user,
                    submitted_at__gte=self.shift_start,
                    submitted_at__lt=self.shift_end,
                )
                submitted = subs.filter(workflow_state=WorkflowState.SUBMITTED)
                
                stats.append({
                    'user': user,
                    'total': subs.count(),
                    'submitted': submitted.count(),
                    'avg_severity': submitted.aggregate(avg=Avg('severity_score'))['avg'] or 0,
                    'missed': MissedFormAlert.objects.filter(
                        user=user, created_at__date=self.today
                    ).count(),
                })
            except User.DoesNotExist:
                continue
        
        return stats
    
    def _get_shop_breakdown(self, plants, submitted=None):
        """Get breakdown by shop"""
        if submitted is None:
            submitted = Submission.objects.filter(
                plant__in=plants,
                submitted_at__gte=self.shift_start,
                submitted_at__lt=self.shift_end,
                workflow_state__in=[WorkflowState.SUBMITTED, WorkflowState.CLOSED]
            )
        
        shops = Shop.objects.filter(plant__in=plants, is_active=True)
        breakdown = []
        
        for shop in shops:
            shop_subs = submitted.filter(shop=shop)
            breakdown.append({
                'shop': shop,
                'plant': shop.plant,
                'submissions': shop_subs.count(),
                'avg_severity': shop_subs.aggregate(avg=Avg('severity_score'))['avg'] or 0,
                'open_issues': shop_subs.filter(severity_score__gte=8).count(),
            })
        
        return breakdown
    
    def _get_line_breakdown(self, plants, submitted=None):
        """Get breakdown by line"""
        if submitted is None:
            submitted = Submission.objects.filter(
                plant__in=plants,
                submitted_at__gte=self.shift_start,
                submitted_at__lt=self.shift_end,
                workflow_state__in=[WorkflowState.SUBMITTED, WorkflowState.CLOSED]
            )
        
        lines = Line.objects.filter(shop__plant__in=plants, is_active=True)
        breakdown = []
        
        for line in lines:
            line_subs = submitted.filter(line=line)
            breakdown.append({
                'line': line,
                'shop': line.shop,
                'plant': line.shop.plant,
                'submissions': line_subs.count(),
                'avg_severity': line_subs.aggregate(avg=Avg('severity_score'))['avg'] or 0,
                'open_issues': line_subs.filter(severity_score__gte=8).count(),
            })
        
        return breakdown
    
    def _get_weekly_trend(self, plants):
        """Get 7-day trend data"""
        trend = []
        for i in range(7):
            date = self.today - timedelta(days=i)
            day_start = timezone.make_aware(
                datetime.combine(date, timezone.datetime.strptime("08:00", "%H:%M").time())
            )
            day_end = day_start + timedelta(days=1)
            
            count = Submission.objects.filter(
                plant__in=plants,
                submitted_at__gte=day_start,
                submitted_at__lt=day_end,
                workflow_state__in=[WorkflowState.SUBMITTED, WorkflowState.CLOSED]
            ).count()
            
            trend.append({
                'date': date,
                'count': count,
                'day_name': date.strftime('%a'),
            })
        
        return list(reversed(trend))
    
    def _get_severity_distribution(self, submissions):
        """Get severity score distribution"""
        distribution = {
            'low': submissions.filter(severity_score__lte=3).count(),
            'medium': submissions.filter(severity_score__gt=3, severity_score__lt=8).count(),
            'high': submissions.filter(severity_score__gte=8).count(),
        }
        return distribution