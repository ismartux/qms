class PlantDatabaseRouter:
    def db_for_read(self, model, **hints):
        request = hints.get("request")
        if not request:
            return None

        plant = getattr(request, "plant", None)
        if not plant:
            return None

        return f"plant_{plant.code.lower()}"

    def db_for_write(self, model, **hints):
        return self.db_for_read(model, **hints)

    def allow_relation(self, obj1, obj2, **hints):
        return True

    def allow_migrate(self, db, app_label, model_name=None, **hints):
        return True