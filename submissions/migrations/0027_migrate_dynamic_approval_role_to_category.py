from django.db import migrations


def forwards(apps, schema_editor):
    Approval = apps.get_model("submissions", "DynamicSubmissionApproval")
    ApprovalCategory = apps.get_model("identity", "ApprovalCategory")
    Role = apps.get_model("identity", "Role")

    for approval in Approval.objects.all():
        if hasattr(approval, "role") and approval.role:
            category = ApprovalCategory.objects.filter(code=approval.role).first()
            role = Role.objects.filter(code=approval.role).first()

            approval.category = category
            approval.approver_role = role
            approval.save(update_fields=["category", "approver_role"])


class Migration(migrations.Migration):

    dependencies = [
        ('submissions', '0026_alter_dynamicsubmissionapproval_options_and_more'),
    ]

    operations = [
        migrations.RunPython(forwards),
    ]