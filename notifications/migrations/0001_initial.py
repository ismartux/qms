from django.db import migrations, models

class Migration(migrations.Migration):
    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="LarkConfig",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(help_text="Friendly identifier for this Lark bot configuration", max_length=100, unique=True)),
                ("webhook_url", models.URLField(help_text="Full webhook URL for the Lark group (e.g. https://open.larksuite.com/open-apis/... )")),
            ],
            options={
                "verbose_name": "Lark Configuration",
                "verbose_name_plural": "Lark Configurations",
            },
        ),
    ]
