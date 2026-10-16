import json
import logging
from django.db import connection
from django.utils import timezone

logger = logging.getLogger(__name__)


def get_dcc_department_id_by_code(dept_code):
    """
    Look up department ID in dcc.core_department by department code.
    Defaults to 1 ('DCC') if not found.
    """
    if not dept_code:
        return 1

    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT id FROM dcc.core_department WHERE UPPER(code) = UPPER(%s) LIMIT 1",
            [dept_code.strip()]
        )
        row = cursor.fetchone()
        if row:
            return row[0]
        # Fallback to DCC department
        return 1


def sync_qms_user_to_dcc(user, profile=None):
    """
    Synchronizes a QMS User and EmployeeProfile to dcc.core_user in the PostgreSQL database.
    Guarantees strict RBAC and prevents unauthorized access.
    """
    if not user:
        return False

    if profile is None:
        profile = getattr(user, 'employee_profile', None)

    username = user.username.strip()
    employee_id = getattr(profile, 'employee_id', username) if profile else username

    is_superuser = user.is_superuser
    has_dcc_access = is_superuser or (profile and getattr(profile, 'dcc_access', False))

    # If the user does not have DCC access, revoke their DCC active status
    if not has_dcc_access:
        with connection.cursor() as cursor:
            cursor.execute(
                "UPDATE dcc.core_user SET is_active = FALSE WHERE username = %s OR employee_id = %s",
                [username, employee_id]
            )
        logger.info(f"DCC access deactivated for user {username}")
        return True

    # Determine assigned DCC Role
    if is_superuser:
        dcc_role = 'ADMIN'
    else:
        dcc_role = getattr(profile, 'dcc_role', 'USER') or 'USER'

    dept_code = getattr(profile, 'dcc_department_code', '') if profile else ''
    if not dept_code and dcc_role in ['ADMIN', 'DCC_MAM']:
        dept_code = 'DCC'
    dept_id = get_dcc_department_id_by_code(dept_code)

    is_hod = bool(getattr(profile, 'dcc_is_hod', False)) or (dcc_role == 'HOD')
    is_am = bool(getattr(profile, 'dcc_is_am', False)) or (dcc_role in ['DEPT_AM', 'SUPERVISOR_AM', 'QA_SUPERVISOR_AM'])
    is_active = bool(user.is_active)
    is_staff = bool(user.is_staff or is_superuser or dcc_role == 'ADMIN')
    dcc_roles_json = json.dumps([dcc_role] if dcc_role else [])

    with connection.cursor() as cursor:
        # Check if record already exists in dcc.core_user
        cursor.execute(
            "SELECT id FROM dcc.core_user WHERE username = %s OR (employee_id IS NOT NULL AND employee_id = %s) LIMIT 1",
            [username, employee_id]
        )
        existing = cursor.fetchone()

        if existing:
            dcc_user_id = existing[0]
            cursor.execute(
                """
                UPDATE dcc.core_user
                SET password = %s,
                    email = %s,
                    first_name = %s,
                    last_name = %s,
                    is_active = %s,
                    is_staff = %s,
                    is_superuser = %s,
                    role = %s,
                    roles = CASE WHEN roles IS NULL OR roles = '[]'::jsonb THEN %s::jsonb ELSE roles END,
                    department_id = %s,
                    employee_id = %s,
                    is_hod = %s,
                    is_am = %s
                WHERE id = %s
                """,
                [
                    user.password,
                    user.email or '',
                    user.first_name or '',
                    user.last_name or '',
                    is_active,
                    is_staff,
                    is_superuser,
                    dcc_role,
                    dcc_roles_json,
                    dept_id,
                    employee_id,
                    is_hod,
                    is_am,
                    dcc_user_id
                ]
            )
            logger.info(f"Updated user {username} in dcc.core_user (Role={dcc_role}, Dept={dept_id})")
        else:
            now = timezone.now()
            cursor.execute(
                """
                INSERT INTO dcc.core_user (
                    password, username, first_name, last_name, email,
                    is_staff, is_active, is_superuser, date_joined,
                    role, roles, designation, phone, signature_status,
                    department_id, employee_id, is_hod, is_am
                ) VALUES (
                    %s, %s, %s, %s, %s,
                    %s, %s, %s, %s,
                    %s, %s, %s, %s, %s,
                    %s, %s, %s, %s
                )
                """,
                [
                    user.password,
                    username,
                    user.first_name or '',
                    user.last_name or '',
                    user.email or '',
                    is_staff,
                    is_active,
                    is_superuser,
                    now,
                    dcc_role,
                    dcc_roles_json,
                    '',
                    '',
                    'NOT_CONFIGURED',
                    dept_id,
                    employee_id,
                    is_hod,
                    is_am
                ]
            )
            logger.info(f"Created new user {username} in dcc.core_user (Role={dcc_role}, Dept={dept_id})")

    return True


def initial_bidirectional_sync():
    """
    1. Provisions QMS superuser (mrsingh) in DCC as ADMIN.
    2. Imports all existing DCC users into QMS EmployeeProfile directory.
    """
    from django.contrib.auth.models import User
    from core.identity.models import EmployeeProfile, Permission, Role, RolePermission

    # 1. Ensure all QMS superusers (including mrsingh29, mrsingh, 19105271, etc.) have profiles & DCC ADMIN access
    for superuser in User.objects.filter(is_superuser=True):
        profile, _ = EmployeeProfile.objects.get_or_create(
            user=superuser,
            defaults={'employee_id': superuser.username}
        )
        profile.dcc_access = True
        profile.dcc_role = 'ADMIN'
        profile.dcc_department_code = 'DCC'
        profile.save()
        sync_qms_user_to_dcc(superuser, profile)
        print(f"✓ Provisioned QMS superuser {superuser.username} to DCC as ADMIN")

    # 1b. Ensure every non-superuser also has an EmployeeProfile
    for non_super in User.objects.filter(is_superuser=False, employee_profile__isnull=True):
        EmployeeProfile.objects.create(
            user=non_super,
            employee_id=non_super.username
        )

    # 2. Read existing DCC users and sync to QMS
    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT u.id, u.username, u.email, u.first_name, u.last_name,
                   u.password, u.is_active, u.is_staff, u.is_superuser,
                   u.role, u.employee_id, u.is_hod, u.is_am, d.code
            FROM dcc.core_user u
            LEFT JOIN dcc.core_department d ON u.department_id = d.id
            """
        )
        dcc_users = cursor.fetchall()

    imported_count = 0
    updated_count = 0

    for row in dcc_users:
        (
            d_id, d_username, d_email, d_first, d_last,
            d_pwd, d_active, d_staff, d_super,
            d_role, d_empid, d_is_hod, d_is_am, dept_code
        ) = row

        emp_id = d_empid or d_username

        user = User.objects.filter(username=d_username).first()
        if not user and d_empid:
            user = User.objects.filter(username=d_empid).first()

        if not user:
            user = User.objects.create(
                username=d_username,
                email=d_email or '',
                first_name=d_first or '',
                last_name=d_last or '',
                is_active=d_active,
                is_staff=d_staff,
                is_superuser=d_super,
                password=d_pwd  # Keep existing hash
            )
            imported_count += 1
        else:
            updated_count += 1

        profile, _ = EmployeeProfile.objects.get_or_create(
            user=user,
            defaults={'employee_id': emp_id}
        )
        profile.dcc_access = True
        profile.dcc_role = d_role
        profile.dcc_department_code = dept_code or 'DCC'
        profile.dcc_is_hod = bool(d_is_hod)
        profile.dcc_is_am = bool(d_is_am)
        profile.save()

    print(f"✓ DCC User Sync Complete: {imported_count} imported, {updated_count} updated.")
    return imported_count, updated_count

