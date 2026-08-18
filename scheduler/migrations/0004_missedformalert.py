# Generated migration for MissedFormAlert model
from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone

class Migration(migrations.Migration):

    dependencies = [
        ('scheduler', '0003_alter_scheduledinstance_created_submission_id'),
        ('forms_engine', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='MissedFormAlert',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('expected_at', models.DateTimeField()),
                ('notification_sent', models.BooleanField(default=False)),
                ('group_alert_sent', models.BooleanField(default=False)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('instance', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='missed_alerts', to='scheduler.scheduledinstance')),
                ('template', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='missed_alerts', to='forms_engine.checklisttemplate')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='missed_form_alerts', to='auth.User')),
            ],
            options={
                'ordering': ['-created_at'],
                'indexes': [models.Index(fields=['user', 'notification_sent'], name='scheduler_m_user_id_123456_idx'), models.Index(fields=['created_at'], name='scheduler_m_created_123456_idx')],
                'unique_together': {('instance', 'user')},
            },
        ),
    ]