from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('submissions', '0027_migrate_dynamic_approval_role_to_category'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='dynamicsubmissionapproval',
            options={'ordering': ['created_at']},
        ),
        migrations.AlterUniqueTogether(
            name='dynamicsubmissionapproval',
            unique_together={('submission', 'category')},
        ),
        migrations.RemoveField(
            model_name='dynamicsubmissionapproval',
            name='role',
        ),
    ]