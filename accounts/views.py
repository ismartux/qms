from django.contrib.auth import authenticate, login, logout
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import csrf_protect
from django.db import transaction
from django.conf import settings
import threading
from accounts.decorators import admin_required
from core.identity.models import UserScope, Role, Department, EmployeeProfile
from core.identity.services import generate_employee_password
from org.models import Plant
from integrations.bitable.user_service import sync_user_to_bitable
from integrations.bitable.upsert_client import upsert_bitable_record_via_relay
from django.utils import timezone


def login_view(request):
    # Prevent logged-in users from seeing login page
    if request.user.is_authenticated:
        return redirect("/")

    if request.method == "POST":
        username = request.POST.get("username")
        password = request.POST.get("password")

        user = authenticate(request, username=username, password=password)

        if user is not None:
            login(request, user)
            # 🔑 RESPECT 'next' PARAMETER (from @login_required redirect)
            # This ensures users are redirected back to the approval page
            # after login, instead of being sent to the home page.
            next_url = request.POST.get("next") or request.GET.get("next")
            if next_url:
                return redirect(next_url)
            return redirect("/")
        else:
            messages.error(request, "Invalid username or password")

    return render(request, "accounts/login.html")


@login_required
def logout_view(request):
    logout(request)
    return redirect("/login/")


# =====================================================
# USER LIST
# =====================================================

@admin_required
def user_management(request):
    users = (
        User.objects
        .filter(is_superuser=False)
        .filter(employee_profile__isnull=False)
        .select_related("employee_profile")
        .prefetch_related(
            "scopes__plant",
            "scopes__department",
            "scopes__role",
        )
        .order_by("username")
    )

    return render(request, "accounts/user_management.html", {
        "users": users
    })


# =====================================================
# USER CREATE
# =====================================================

@admin_required
def user_create(request):
    if request.method == "POST":

        employee_id = request.POST.get("employee_id", "").strip()
        first_name = request.POST.get("first_name", "").strip()
        last_name = request.POST.get("last_name", "").strip()
        email = request.POST.get("email", "").strip()

        # ---- VALIDATION ----
        if not employee_id:
            messages.error(request, "Employee ID is required")
            return redirect("accounts:user_create")

        if User.objects.filter(username=employee_id).exists():
            messages.error(request, "Employee ID already exists")
            return redirect("accounts:user_create")

        if EmployeeProfile.objects.filter(employee_id=employee_id).exists():
            messages.error(request, "Employee ID already exists")
            return redirect("accounts:user_create")

        try:
            with transaction.atomic():

                # ---- USER ----
                user = User(
                    username=employee_id,
                    email=email,
                    first_name=first_name,
                    last_name=last_name,
                    is_active=("is_active" in request.POST),
                    is_staff=("is_staff" in request.POST),
                )

                raw_password = generate_employee_password(first_name, employee_id)
                user.set_password(raw_password)
                user.full_clean()
                user.save()

                # ---- EMPLOYEE PROFILE ----
                EmployeeProfile.objects.create(
                    user=user,
                    employee_id=employee_id
                )

                # ---- USER SCOPE ----
                scope = UserScope.objects.create(
                    user=user,
                    plant_id=request.POST.get("plant"),
                    department_id=request.POST.get("department"),
                    role_id=request.POST.get("role"),
                )

        except Exception as e:
            messages.error(request, f"Error creating user: {e}")
            return redirect("accounts:user_create")

        # =====================================================
        # 🔥 BITABLE SYNC (NON-BLOCKING - CLOUDFLARE RELAY)
        # =====================================================
        def _sync_user():
            try:
                sync_user_to_bitable(
                    user=user,
                    raw_password=raw_password,
                    scope=scope,
                    app_token=settings.BITABLE_USER_APP_TOKEN,
                    table_id=settings.BITABLE_USER_TABLE_ID,
                    created_by=request.user,
                )
            except Exception as e:
                print("Bitable user sync failed:", e)

        threading.Thread(target=_sync_user, daemon=True).start()

        # ---- SHOW PASSWORD ONCE ----
        request.session["created_user_credentials"] = {
            "username": user.username,
            "password": raw_password,
        }

        return redirect("accounts:user_created_success")

    return render(request, "accounts/user_create.html", {
        "plants": Plant.objects.select_related("company"),
        "roles": Role.objects.filter(is_active=True),
    })


# =====================================================
# USER CREATED SUCCESS
# =====================================================

@admin_required
def user_created_success(request):
    creds = request.session.pop("created_user_credentials", None)

    if not creds:
        return redirect("accounts:admin_users")

    return render(request, "accounts/user_created_success.html", creds)


# =====================================================
# RESET PASSWORD
# =====================================================

@admin_required
@require_POST
def reset_user_password(request, user_id):

    if not request.user.is_superuser:
        return JsonResponse({"error": "Not allowed"}, status=403)

    user = get_object_or_404(User, id=user_id)

    if not hasattr(user, "employee_profile"):
        return JsonResponse({"error": "Employee profile missing"}, status=400)

    raw_password = generate_employee_password(
        user.first_name,
        user.employee_profile.employee_id
    )

    user.set_password(raw_password)
    user.save(update_fields=["password"])

    scope = UserScope.objects.filter(user=user).first()

    # =====================================================
    # 🔥 UPSERT TO BITABLE (Search + Update)
    # =====================================================
    def _sync_user():
        try:
            fields = {
                "Employee_ID": str(user.username),   # 🔥 match field
                "First_Name": user.first_name or "",
                "Last_Name": user.last_name or "",
                "Email": user.email or "",
                "Password": raw_password,
                "Is_Active": str(user.is_active),
                "Is_Staff": str(user.is_staff),
                "Created_At": int(timezone.now().timestamp() * 1000),
            }

            if scope:
                fields.update({
                    "Plant": scope.plant.name if scope.plant else "",
                    "Department": scope.department.name if scope.department else "",
                    "Role": scope.role.name if scope.role else "",
                })

            upsert_bitable_record_via_relay(
                app_token=settings.BITABLE_USER_APP_TOKEN,
                table_id=settings.BITABLE_USER_TABLE_ID,
                records=[fields],
                match_field="Employee_ID",   # 🔥 worker will search this column
            )

        except Exception as e:
            print("Bitable password reset sync failed:", e)

    threading.Thread(target=_sync_user, daemon=True).start()

    request.session["created_user_credentials"] = {
        "username": user.username,
        "password": raw_password,
    }

    return redirect("accounts:user_created_success")


# =====================================================
# ACTIVATE / DEACTIVATE
# =====================================================

@admin_required
@require_POST
@csrf_protect
def activate_user(request, user_id):
    user = get_object_or_404(User, id=user_id)
    user.is_active = True
    user.save(update_fields=["is_active"])
    return JsonResponse({"success": True})


@admin_required
@require_POST
@csrf_protect
def deactivate_user(request, user_id):
    user = get_object_or_404(User, id=user_id)
    user.is_active = False
    user.save(update_fields=["is_active"])
    return JsonResponse({"success": True})


# =====================================================
# USER EDIT
# =====================================================

@admin_required
def user_edit(request, user_id):

    user = get_object_or_404(User, id=user_id)
    user_scope = UserScope.objects.filter(user=user).first()
    profile, _ = EmployeeProfile.objects.get_or_create(user=user)

    if request.method == "POST":

        new_employee_id = request.POST.get("employee_id", "").strip()

        if not new_employee_id:
            messages.error(request, "Employee ID is required")
            return redirect("accounts:user_edit", user_id=user.id)

        if (
            EmployeeProfile.objects
            .exclude(user=user)
            .filter(employee_id=new_employee_id)
            .exists()
        ):
            messages.error(request, "Employee ID already exists")
            return redirect("accounts:user_edit", user_id=user.id)

        try:
            with transaction.atomic():

                user.username = new_employee_id
                user.email = request.POST.get("email", "").strip()
                user.first_name = request.POST.get("first_name", "").strip()
                user.last_name = request.POST.get("last_name", "").strip()
                user.is_active = ("is_active" in request.POST)
                user.is_staff = ("is_staff" in request.POST)
                user.save()

                profile.employee_id = new_employee_id
                profile.save()

                plant_id = request.POST.get("plant")
                department_id = request.POST.get("department")
                role_id = request.POST.get("role")

                if plant_id and department_id and role_id:
                    if user_scope:
                        user_scope.plant_id = plant_id
                        user_scope.department_id = department_id
                        user_scope.role_id = role_id
                        user_scope.save()
                    else:
                        UserScope.objects.create(
                            user=user,
                            plant_id=plant_id,
                            department_id=department_id,
                            role_id=role_id
                        )

        except Exception:
            messages.error(request, "Failed to update user. Please try again.")
            return redirect("accounts:user_edit", user_id=user.id)

        return redirect("accounts:admin_users")

    return render(request, "accounts/user_edit.html", {
        "edit_user": user,
        "employee_profile": profile,
        "user_scope": user_scope,
        "plants": Plant.objects.select_related("company"),
        "roles": Role.objects.filter(is_active=True),
    })


# =====================================================
# AJAX: GET DEPARTMENTS
# =====================================================

@admin_required
def get_departments(request, plant_id):

    departments = Department.objects.filter(
        plant_id=plant_id
    ).order_by("name")

    return JsonResponse({
        "departments": [
            {"id": d.id, "name": d.name}
            for d in departments
        ]
    })



import csv
import io

@admin_required
def bulk_user_upload(request):

    if request.method == "POST":

        file = request.FILES.get("file")

        if not file:
            messages.error(request, "Please upload a CSV file.")
            return redirect("accounts:bulk_user_upload")

        try:
            decoded_file = file.read().decode("utf-8")
            io_string = io.StringIO(decoded_file)
            reader = csv.DictReader(io_string)
        except Exception:
            messages.error(request, "Invalid CSV file.")
            return redirect("accounts:bulk_user_upload")

        users_data = []
        errors = []

        for row_number, row in enumerate(reader, start=2):

            employee_id = row.get("employee_id", "").strip()

            if not employee_id:
                errors.append(f"Row {row_number}: Missing employee_id")
                continue

            if User.objects.filter(username=employee_id).exists():
                errors.append(f"Row {row_number}: Employee ID already exists")
                continue

            users_data.append({
                "employee_id": employee_id,
                "first_name": row.get("first_name", "").strip(),
                "last_name": row.get("last_name", "").strip(),
                "email": row.get("email", "").strip(),
                "is_active": row.get("is_active", "True") == "True",
                "is_staff": row.get("is_staff", "False") == "True",
            })

        if errors:
            messages.error(request, f"Errors found: {errors}")
            return redirect("accounts:bulk_user_upload")

        request.session["bulk_users_preview"] = users_data

        return redirect("accounts:bulk_user_preview")

    return render(request, "accounts/bulk_user_upload.html")


@admin_required
def bulk_user_preview(request):

    users_data = request.session.get("bulk_users_preview")

    if not users_data:
        return redirect("accounts:bulk_user_upload")

    if request.method == "POST":

        created_users = []

        try:
            with transaction.atomic():

                for index, user_data in enumerate(users_data):

                    employee_id = user_data["employee_id"]

                    plant_id = request.POST.get(f"plant_{index}")
                    department_id = request.POST.get(f"department_{index}")
                    role_id = request.POST.get(f"role_{index}")

                    user = User.objects.create(
                        username=employee_id,
                        email=user_data["email"],
                        first_name=user_data["first_name"],
                        last_name=user_data["last_name"],
                        is_active=user_data["is_active"],
                        is_staff=user_data["is_staff"],
                    )

                    raw_password = generate_employee_password(
                        user.first_name,
                        employee_id
                    )

                    user.set_password(raw_password)
                    user.save()

                    EmployeeProfile.objects.create(
                        user=user,
                        employee_id=employee_id
                    )

                    scope = UserScope.objects.create(
                        user=user,
                        plant_id=plant_id,
                        department_id=department_id,
                        role_id=role_id,
                    )

                    created_users.append((user, raw_password, scope))

        except Exception as e:
            messages.error(request, f"Creation failed: {e}")
            return redirect("accounts:bulk_user_upload")

        # 🔥 Background Bitable Sync
        import threading

        def _sync():
            for user, raw_password, scope in created_users:
                try:
                    sync_user_to_bitable(
                        user=user,
                        raw_password=raw_password,
                        scope=scope,
                        app_token=settings.BITABLE_USER_APP_TOKEN,
                        table_id=settings.BITABLE_USER_TABLE_ID,
                        created_by=request.user,
                    )
                except Exception as e:
                    print("Bulk Bitable sync failed:", e)

        threading.Thread(target=_sync, daemon=True).start()

        request.session.pop("bulk_users_preview", None)

        messages.success(request, f"{len(created_users)} users created successfully.")
        return redirect("accounts:admin_users")

    return render(request, "accounts/bulk_user_preview.html", {
        "users_data": users_data,
        "plants": Plant.objects.all(),
        "roles": Role.objects.filter(is_active=True),
    })




@admin_required
@require_POST
@csrf_protect
def delete_user(request, user_id):

    user = get_object_or_404(User, id=user_id)

    # Prevent self delete
    if user == request.user:
        return JsonResponse({"success": False, "message": "You cannot delete yourself."}, status=400)

    # Prevent deleting superusers (optional safety)
    if user.is_superuser:
        return JsonResponse({"success": False, "message": "Cannot delete superuser."}, status=400)

    user.delete()

    return JsonResponse({"success": True})