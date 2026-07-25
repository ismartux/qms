from django.db import models
from core.tenant.context import get_current_plant


class PlantAwareQuerySet(models.QuerySet):
    def for_current_plant(self):
        """
        Optional explicit plant filter.
        Safe to call manually.
        """
        plant = get_current_plant()
        if plant and hasattr(self.model, "plant"):
            return self.filter(plant=plant)
        return self


class PlantAwareManager(models.Manager):
    def get_queryset(self):
        """
        Automatically apply plant isolation at queryset root.
        DO NOT override filter(), all(), or exclude().
        """
        qs = super().get_queryset()

        plant = get_current_plant()
        if plant and hasattr(self.model, "plant"):
            return qs.filter(plant=plant)

        return qs

    def for_current_plant(self):
        return self.get_queryset()