from django.db import models

class LarkConfig(models.Model):
    """Stores Lark webhook URL for a group bot. Managed via Django admin – no hard‑coding."""
    name = models.CharField(max_length=100, unique=True, help_text="Friendly identifier for this Lark bot configuration")
    webhook_url = models.URLField(help_text="Full webhook URL for the Lark group (e.g. https://open.larksuite.com/open-apis/... )")

    class Meta:
        verbose_name = "Lark Configuration"
        verbose_name_plural = "Lark Configurations"

    def __str__(self):
        return self.name

class BitableConfig(models.Model):
    """Stores Bitable credentials for integration. Managed via Django admin."""
    name = models.CharField(max_length=100, unique=True, help_text="Friendly identifier for the Bitable configuration")
    app_token = models.CharField(max_length=255, help_text="Bitable App Token")
    table_id = models.CharField(max_length=255, help_text="Bitable Table ID")

    class Meta:
        verbose_name = "Bitable Configuration"
        verbose_name_plural = "Bitable Configurations"

    def __str__(self):
        return self.name
