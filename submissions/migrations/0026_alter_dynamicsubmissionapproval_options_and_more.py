# submissions/migrations/0026_add_category_and_approver_role.py

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('identity', '0013_approvalcategory_remove_role_category_and_more'),
        ('submissions', '0025_alter_submission_public_approval_token'),
    ]

    operations = [
        migrations.AddField(
            model_name='dynamicsubmissionapproval',
            name='category',
            field=models.ForeignKey(
                to='identity.approvalcategory',
                on_delete=django.db.models.deletion.PROTECT,
                null=True,
                blank=True,
                related_name='dynamic_approvals',
            ),
        ),
        migrations.AddField(
            model_name='dynamicsubmissionapproval',
            name='approver_role',
            field=models.ForeignKey(
                to='identity.role',
                on_delete=django.db.models.deletion.PROTECT,
                null=True,
                blank=True,
                related_name='dynamic_approvals',
            ),
        ),
    ]