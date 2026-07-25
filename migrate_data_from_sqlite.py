import os
import sys
import django

# Set up Django environment
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

from django.conf import settings

if "sqlite_db" not in settings.DATABASES:
    settings.DATABASES["sqlite_db"] = {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": settings.BASE_DIR / "db.sqlite3",
    }

django.setup()

from django.db import connection, transaction
from django.contrib.auth.models import User
from core.identity.models import (
    Role,
    ApprovalCategory,
    Permission,
    RolePermission,
    EmployeeProfile,
)
from org.models import (
    Company,
    Plant,
    Department,
    Shop,
    Line,
    Station,
    Product,
)
from forms_engine.models import (
    ChecklistTemplate,
    ChecklistApprovalStep,
    ChecklistVersion,
    ChecklistSection,
    ChecklistItem,
    ChecklistItemOption,
    ChecklistRule,
    TemplateRole,
)
from dynamic_forms.models import (
    DynamicFormTemplate,
    DynamicFormVersion,
    DynamicFormField,
    DynamicFormStandardRule,
    DynamicTemplateRole,
)
from ehs_engine.models import (
    EHSFormTemplate,
    EHSFormVersion,
    EHSSection,
    EHSItem,
    EHSItemOption,
    EHSRule,
)
from submissions.models import (
    WorkContext,
    Submission,
    SubmissionResponse,
    SubmissionAttachment,
    SubmissionApproval,
    DynamicFormSubmission,
    DynamicFormSubmissionValue,
)
from capa.models import CAPA
from core.audit.models import AuditLog, DomainEvent


def copy_objects(model, select_related=None, m2m_fields=None):
    """
    Copies all instances of a model from sqlite_db to default (PostgreSQL).
    """
    sqlite_qs = model.objects.using("sqlite_db").all()
    if select_related:
        sqlite_qs = sqlite_qs.select_related(*select_related)

    count = sqlite_qs.count()
    print(f"Migrating {model._meta.verbose_name_plural} ({model.__name__}): {count} records...")

    existing_ids = set(model.objects.using("default").values_list("pk", flat=True))
    to_create = []

    with transaction.atomic(using="default"):
        for obj in sqlite_qs:
            pk_val = obj.pk
            if pk_val not in existing_ids:
                to_create.append(obj)

        if to_create:
            model.objects.using("default").bulk_create(to_create, batch_size=1000, ignore_conflicts=True)

        if m2m_fields:
            for obj in sqlite_qs:
                for field in m2m_fields:
                    sqlite_m2m = getattr(obj, field).all()
                    target_m2m = getattr(obj, field)
                    target_m2m.set(sqlite_m2m)

    print(f"✓ {model.__name__} migration complete.")


def reset_pg_sequences():
    """
    Resets auto-increment sequences in PostgreSQL for tables with integer PKs.
    """
    print("\nResetting PostgreSQL primary key sequences...")
    cursor = connection.cursor()
    cursor.execute("""
        SELECT table_name, column_name, column_default
        FROM information_schema.columns
        WHERE table_schema = 'public'
          AND column_default LIKE 'nextval%';
    """)
    sequences = cursor.fetchall()

    for table, col, default_val in sequences:
        seq_name = default_val.split("'")[1]
        try:
            cursor.execute(f"SELECT setval('{seq_name}', COALESCE((SELECT MAX({col}) FROM {table}), 1));")
            print(f"  Reset sequence '{seq_name}' for table '{table}'")
        except Exception as e:
            print(f"  Error resetting sequence '{seq_name}': {e}")


def main():
    print("=========================================================")
    print("STARTING DATA MIGRATION: SQLite -> PostgreSQL (qms)")
    print("=========================================================\n")

    # 1. Auth & Identity
    copy_objects(User)
    copy_objects(Role, m2m_fields=["approval_categories"])
    copy_objects(ApprovalCategory)
    copy_objects(Permission)
    copy_objects(RolePermission)
    copy_objects(EmployeeProfile)

    # 2. Organization Structure
    copy_objects(Company)
    copy_objects(Plant)
    copy_objects(Department)
    copy_objects(Shop)
    copy_objects(Line)
    copy_objects(Station)
    copy_objects(Product)

    # 3. Forms Engine (Checklist Templates)
    copy_objects(ChecklistTemplate, m2m_fields=["plants", "shops", "products"])
    copy_objects(ChecklistApprovalStep)
    copy_objects(ChecklistVersion)
    copy_objects(ChecklistSection)
    copy_objects(ChecklistItem)
    copy_objects(ChecklistItemOption)
    copy_objects(ChecklistRule)
    copy_objects(TemplateRole)

    # 4. Dynamic Forms
    copy_objects(DynamicFormTemplate, m2m_fields=["plants", "shops", "products"])
    copy_objects(DynamicFormVersion)
    copy_objects(DynamicFormField)
    copy_objects(DynamicFormStandardRule)
    copy_objects(DynamicTemplateRole)

    # 5. EHS Engine
    copy_objects(EHSFormTemplate, m2m_fields=["plants"])
    copy_objects(EHSFormVersion)
    copy_objects(EHSSection)
    copy_objects(EHSItem)
    copy_objects(EHSItemOption)
    copy_objects(EHSRule)

    # 6. Submissions & CAPA
    copy_objects(WorkContext)
    copy_objects(Submission)
    copy_objects(SubmissionResponse)
    copy_objects(SubmissionAttachment)
    copy_objects(SubmissionApproval)
    copy_objects(DynamicFormSubmission)
    copy_objects(DynamicFormSubmissionValue)
    copy_objects(CAPA)
    copy_objects(AuditLog)
    copy_objects(DomainEvent)

    # Reset sequences in Postgres
    reset_pg_sequences()

    print("\n=========================================================")
    print("MIGRATION COMPLETED SUCCESSFULLY!")
    print("=========================================================")


if __name__ == "__main__":
    main()
