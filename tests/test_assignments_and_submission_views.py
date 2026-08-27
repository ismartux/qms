from django.test import TestCase, Client
from django.contrib.auth import get_user_model
from django.urls import reverse
from org.models import Company, Plant, Floor, Shop, Line, FloorTLAssignment, ShopPQEAssignment, IPQCMapping
from submissions.models import Submission, WorkContext
from forms_engine.models import ChecklistTemplate, ChecklistVersion
from submissions.assignment_resolver import resolve_submission_assignments, get_active_tls_for_floor, get_active_pqes_for_shop, get_ipqc_mapping_for_user

User = get_user_model()


class AssignmentAndSubmissionViewTestCase(TestCase):
    def setUp(self):
        self.user_tl = User.objects.create_user(username="tl_user", password="password123", first_name="Tom", last_name="Lead")
        self.user_pqe = User.objects.create_user(username="pqe_user", password="password123", first_name="Penny", last_name="Quality")
        self.user_ipqc = User.objects.create_user(username="ipqc_user", password="password123", first_name="Ian", last_name="QC")
        self.superuser = User.objects.create_superuser(username="admin_user", password="password123", email="admin@example.com")

        self.company = Company.objects.create(code="COMP1", name="Test Company")
        self.plant = Plant.objects.create(company=self.company, code="PL1", name="Test Plant")
        self.shop = Shop.objects.create(plant=self.plant, code="SHOP1", name="SMT Shop")
        
        self.floor = Floor.objects.create(plant=self.plant, code="FL1", name="1st Floor")
        self.line = Line.objects.create(shop=self.shop, floor=self.floor, code="L1", name="SMT Line 1")

        # 1. Floor-wise TL Assignment
        self.tl_assign = FloorTLAssignment.objects.create(
            floor=self.floor,
            user=self.user_tl,
            shift="DAY",
            is_active=True,
        )

        # 2. Shop-wise PQE Assignment
        self.pqe_assign = ShopPQEAssignment.objects.create(
            shop=self.shop,
            user=self.user_pqe,
            is_active=True,
        )

        # 3. IPQC Mapping
        self.ipqc_mapping = IPQCMapping.objects.create(
            user=self.user_ipqc,
            plant=self.plant,
            floor=self.floor,
            shop=self.shop,
            shift="DAY",
            is_active=True,
        )
        self.ipqc_mapping.lines.add(self.line)

    def test_assignments_and_resolvers(self):
        tls = get_active_tls_for_floor(self.floor, shift="DAY")
        self.assertEqual(len(tls), 1)
        self.assertEqual(tls[0], self.user_tl)

        pqes = get_active_pqes_for_shop(self.shop)
        self.assertEqual(len(pqes), 1)
        self.assertEqual(pqes[0], self.user_pqe)

        mapping = get_ipqc_mapping_for_user(self.user_ipqc)
        self.assertIsNotNone(mapping)
        self.assertEqual(mapping.floor, self.floor)
        self.assertEqual(mapping.shop, self.shop)

        active_tls = mapping.get_active_tls()
        self.assertEqual(active_tls.count(), 1)
        self.assertEqual(active_tls.first().user, self.user_tl)

        active_pqes = mapping.get_active_pqes()
        self.assertEqual(active_pqes.count(), 1)
        self.assertEqual(active_pqes.first().user, self.user_pqe)

    def test_submission_assignment_resolution(self):
        from org.models import Department
        self.department = Department.objects.create(plant=self.plant, code="QA", name="Quality Assurance")
        template = ChecklistTemplate.objects.create(code="TMPL_TEST", name="SMT Inspection Form", department=self.department)
        version = ChecklistVersion.objects.create(template=template, version_number=1, is_active=True, is_published=True)

        submission = Submission.objects.create(
            template_version=version,
            plant=self.plant,
            floor=self.floor,
            shop=self.shop,
            line=self.line,
            submitted_by=self.user_ipqc,
        )

        resolved = resolve_submission_assignments(submission)
        self.assertEqual(resolved["floor_name"], "1st Floor")
        self.assertEqual(resolved["shop_name"], "SMT Shop")
        self.assertIn("Tom Lead", resolved["tl_names"])
        self.assertIn("Penny Quality", resolved["pqe_names"])

    def test_submission_list_view_filters(self):
        client = Client()
        client.force_login(self.superuser)

        url = reverse("ui:submission_list")
        
        # Test flat view
        response = client.get(url, {"view_mode": "flat"})
        self.assertEqual(response.status_code, 200)

        # Test line-wise view
        response = client.get(url, {"view_mode": "by_line", "line_id": self.line.id})
        self.assertEqual(response.status_code, 200)

        # Test ipqc-wise view
        response = client.get(url, {"view_mode": "by_ipqc", "ipqc_id": self.user_ipqc.id})
        self.assertEqual(response.status_code, 200)

    def test_pqe_scope_restrictions(self):
        from core.identity.models import Role, UserScope, Permission, RolePermission, ApprovalCategory
        from org.models import Department
        from submissions.assignment_resolver import can_pqe_view_or_approve_submission, filter_submissions_for_pqe_scope

        # Create PQE role and assign to user_pqe
        pqe_role, _ = Role.objects.get_or_create(code="PQE", defaults={"name": "Product Quality Engineer"})
        perm, _ = Permission.objects.get_or_create(code="can_approve_ipqc", defaults={"name": "Can Approve IPQC"})
        RolePermission.objects.get_or_create(role=pqe_role, permission=perm)
        dept, _ = Department.objects.get_or_create(plant=self.plant, code="QA", defaults={"name": "Quality"})
        UserScope.objects.create(user=self.user_pqe, role=pqe_role, plant=self.plant, department=dept)

        # Another shop & line outside user_pqe's assignment
        other_shop = Shop.objects.create(plant=self.plant, code="SHOP_PACK", name="Packaging Shop")
        other_line = Line.objects.create(shop=other_shop, floor=self.floor, code="L_OTHER", name="Packaging Line 1")
        other_ipqc = User.objects.create_user(username="other_ipqc", password="password123")

        template = ChecklistTemplate.objects.create(code="TMPL_SCOPED", name="Inspection Form", department=dept)
        version = ChecklistVersion.objects.create(template=template, version_number=1, is_active=True, is_published=True)

        from django.utils import timezone
        from core.workflow.states import WorkflowState
        from forms_engine.models import ChecklistApprovalStep

        cat, _ = ApprovalCategory.objects.get_or_create(code="PQE", defaults={"name": "PQE Approval", "is_approver": True})
        ChecklistApprovalStep.objects.create(template=template, category=cat, order=1)

        # Submission 1: in assigned SMT Shop
        sub_allowed = Submission.objects.create(
            template_version=version,
            plant=self.plant,
            floor=self.floor,
            shop=self.shop,
            line=self.line,
            submitted_by=self.user_ipqc,
            submitted_at=timezone.now(),
            workflow_state=WorkflowState.SUBMITTED,
        )

        # Submission 2: in Packaging Shop (not assigned to user_pqe)
        sub_blocked = Submission.objects.create(
            template_version=version,
            plant=self.plant,
            floor=self.floor,
            shop=other_shop,
            line=other_line,
            submitted_by=other_ipqc,
            submitted_at=timezone.now(),
            workflow_state=WorkflowState.SUBMITTED,
        )

        # Test can_pqe_view_or_approve_submission
        self.assertTrue(can_pqe_view_or_approve_submission(self.user_pqe, sub_allowed))
        self.assertFalse(can_pqe_view_or_approve_submission(self.user_pqe, sub_blocked))

        # Test filter_submissions_for_pqe_scope queryset filter
        all_subs = Submission.objects.filter(submission_id__in=[sub_allowed.submission_id, sub_blocked.submission_id])
        filtered_subs = filter_submissions_for_pqe_scope(self.user_pqe, all_subs)
        self.assertEqual(filtered_subs.count(), 1)
        self.assertEqual(filtered_subs.first(), sub_allowed)

        # Test UI View with PQE logged in
        client = Client()
        client.force_login(self.user_pqe)
        url = reverse("ui:submission_list")
        resp = client.get(url)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.context["submissions"]), 1)
        self.assertEqual(resp.context["submissions"][0]["id"], sub_allowed.submission_id)

        # Test approve_submission endpoint scoping
        cat, _ = ApprovalCategory.objects.get_or_create(code="PQE", defaults={"name": "PQE Approval", "is_approver": True})
        
        # Test approval_pending_dashboard: PQE user only sees sub_allowed in pending approvals
        resp_pending = client.get(reverse("ui:approval_pending_dashboard"))
        self.assertEqual(resp_pending.status_code, 200)
        self.assertEqual(len(resp_pending.context["cards"]), 1)
        self.assertEqual(resp_pending.context["cards"][0]["submission"].submission_id, sub_allowed.submission_id)

        # Approving blocked submission outside PQE scope should return 403
        resp_blocked = client.post(
            reverse("ui:approve_submission", args=[sub_blocked.submission_id]),
            {"category": "PQE"}
        )
        self.assertEqual(resp_blocked.status_code, 403)
        self.assertEqual(resp_blocked.json()["error_type"], "SCOPE_BLOCKED")

        # Test CAPA scoping
        from capa.models import CAPA
        capa_allowed = CAPA.objects.create(
            submission=sub_allowed,
            title="Allowed NC",
            description="SMT NC",
            severity=3,
            due_date=timezone.now().date(),
            status="ACTION_DONE",
        )
        capa_blocked = CAPA.objects.create(
            submission=sub_blocked,
            title="Blocked NC",
            description="Packaging NC",
            severity=3,
            due_date=timezone.now().date(),
            status="ACTION_DONE",
        )

        perm_capa, _ = Permission.objects.get_or_create(code="can_manage_capa", defaults={"name": "Can Manage CAPA"})
        RolePermission.objects.get_or_create(role=pqe_role, permission=perm_capa)

        from submissions.assignment_resolver import can_pqe_view_or_approve_capa, filter_capas_for_pqe_scope
        self.assertTrue(can_pqe_view_or_approve_capa(self.user_pqe, capa_allowed))
        self.assertFalse(can_pqe_view_or_approve_capa(self.user_pqe, capa_blocked))

        filtered_capas = filter_capas_for_pqe_scope(self.user_pqe, CAPA.objects.filter(capa_id__in=[capa_allowed.capa_id, capa_blocked.capa_id]))
        self.assertEqual(filtered_capas.count(), 1)
        self.assertEqual(filtered_capas.first(), capa_allowed)

        # Test CAPA pending approvals view
        resp_capa_pending = client.get(reverse("capa:approval_pending_capas"))
        self.assertEqual(resp_capa_pending.status_code, 200)
        self.assertEqual(len(resp_capa_pending.context["capas"]), 1)
        self.assertEqual(resp_capa_pending.context["capas"][0].capa_id, capa_allowed.capa_id)

        # Test CAPA approve endpoint permission denied for blocked capa
        resp_capa_approve_blocked = client.post(reverse("capa:capa_approve", args=[capa_blocked.capa_id]))
        self.assertEqual(resp_capa_approve_blocked.status_code, 403)


