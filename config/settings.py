from pathlib import Path
import os

BASE_DIR = Path(__file__).resolve().parent.parent

# Load .env file if available
env_file = BASE_DIR / ".env"
if env_file.exists():
    with open(env_file, "r") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip())

# SECURITY
SECRET_KEY = os.getenv("DJANGO_SECRET_KEY", "unsafe-dev-key")
DEBUG = os.getenv("DJANGO_DEBUG", os.getenv("DEBUG", "false")).lower() == "true"
allowed_hosts_env = os.getenv("DJANGO_ALLOWED_HOSTS", "qms.ismartux.com,127.0.0.1,localhost")
ALLOWED_HOSTS = [h.strip() for h in allowed_hosts_env.split(",") if h.strip()]

CSRF_TRUSTED_ORIGINS = [
    "https://qms.ismartux.com",
    "http://qms.ismartux.com",
    "https://*.trycloudflare.com",
    "https://mrsingh29.pythonanywhere.com",
    "https://transsflow.onrender.com",
    "http://127.0.0.1:8000",
    "http://localhost:8000",
]

# APPLICATIONS
INSTALLED_APPS = [
    # Django core
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",

    # Platform core
    "core",
    "org",
    "core.identity",
    "core.audit",
    "core.workflow",

    # Business logic
    "forms_engine",
    "submissions.apps.SubmissionsConfig",
    "analytics",
    "capa",
    "scheduler",


    "ehs_engine",
    "dynamic_forms",


    # Integrations
    "integrations",

    "accounts",
    "storages",

    # UI
    "ui",
]

# MIDDLEWARE
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",

    "whitenoise.middleware.WhiteNoiseMiddleware",

    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",

    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",

    # 👇 AFTER authentication (CRITICAL)
    "core.tenant.middleware.PlantIsolationMiddleware",

    # 👇 Plant timezone can safely come after isolation
    "core.middleware.PlantTimezoneMiddleware",

    # 👇 Your custom middlewares
    "core.errors.middleware.GlobalExceptionMiddleware",
    "core.middleware.SessionSanitizerMiddleware",
    "scheduler.middleware.SchedulerMiddleware",

    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

STORAGES = {
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
    },
}

# URLS / TEMPLATES
ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "ui" / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                 # 🔥 THIS LINE MUST EXIST
                "ui.context_processors.ui_context",
                "ui.context_processors.admin_access",  # if you created this
                "core.context_processors.sidebar.permission_context",
                "core.context_processors.context_processors.role_flags",
                'capa.context_processors.global_nav_notifications',
                "ehs_engine.context_processors.notification_context",
            ],
        },
    },
]



WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

# DATABASE
DB_ENGINE = os.getenv("DB_ENGINE", "django.db.backends.postgresql")
DB_NAME = os.getenv("DB_NAME", "qms")
DB_USER = os.getenv("DB_USER", "postgres")
DB_PASSWORD = os.getenv("DB_PASSWORD", "Ismartu.Postgres.Admin@X.0729")
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = os.getenv("DB_PORT", "5432")

DATABASES = {
    "default": {
        "ENGINE": DB_ENGINE,
        "NAME": DB_NAME,
        "USER": DB_USER,
        "PASSWORD": DB_PASSWORD,
        "HOST": DB_HOST,
        "PORT": DB_PORT,
    }
}

DATABASE_ROUTERS = ["core.db_router.PlantDatabaseRouter"]

# AUTH
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
]

LOGIN_URL = "/login/"
LOGIN_REDIRECT_URL = "/app/dashboard/"
LOGOUT_REDIRECT_URL = "/login/"

# STATIC FILES
STATIC_URL = "/static/"

STATICFILES_DIRS = [
    BASE_DIR / "ui" / "static",
]

STATIC_ROOT = BASE_DIR / "staticfiles"

# MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

DATA_UPLOAD_MAX_MEMORY_SIZE = 10 * 1024 * 1024  # 10 MB
FILE_UPLOAD_MAX_MEMORY_SIZE = 10 * 1024 * 1024



# TIME / LOCALE
LANGUAGE_CODE = "en-us"
TIME_ZONE = "Asia/Kolkata"
USE_I18N = True
USE_TZ = True

# SESSION
SESSION_ENGINE = "django.contrib.sessions.backends.db"
SESSION_COOKIE_AGE = 8 * 60 * 60  # 8 hours

# DEFAULTS
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"


LARK_APP_ID = os.getenv("LARK_APP_ID", "cli_a83144a175fad00c")
LARK_APP_SECRET = os.getenv("LARK_APP_SECRET", "")

BITABLE_USER_APP_TOKEN = "YEmXbTeKaa0NOws1mWucq4C9nKh"
BITABLE_USER_TABLE_ID = "tbly9wKgPs4LsgR0"

BITABLE_APPROVAL_APP_TOKEN = "XeKbbjTnqalAh8sno9kcEy6AnVh"
BITABLE_APPROVAL_TABLE_ID = "tbl5PaBHjrjB3ubR"

CAPA_BITABLE_APP_TOKEN = "XeKbbjTnqalAh8sno9kcEy6AnVh"
CAPA_BITABLE_TABLE_ID = "tbl2x0dPtg6ZAOem"

SITE_BASE_URL = "https://mrsingh29.pythonanywhere.com"  # dev


BITABLE_SYNC_MODE = "CLOUDFLARE"
# options:
# "LEGACY"  -> old chunk system
# "CLOUDFLARE" -> instant relay mode

# 🔹 CREATE worker (forms, simple write)
CLOUDFLARE_RELAY_URL = "https://lark-relay.mrsingh2996.workers.dev"
CLOUDFLARE_RELAY_SECRET = "transsflow_secure_2026_very_secret_this_is_pythonanywhere_bitable_external_api_workaround"

# 🔹 UPSERT worker (search + update logic)
CLOUDFLARE_UPSERT_RELAY_URL = "https://lark-update-relay.mrsingh2996.workers.dev"
CLOUDFLARE_UPSERT_RELAY_SECRET = "this_is_transsflow_bitable_update_relay_secrete_code"

CLOUDFLARE_READ_WORKER_URL = "https://bitable-read-worker.mrsingh2996.workers.dev"
CLOUDFLARE_READ_RELAY_SECRET = "this_is_transsflow_bitable_read_relay_secrete_code"
DJANGO_SNAPSHOT_URL = "https://mrsingh29.pythonanywhere.com/bitable/internal/bitable/snapshot/"


# ========== STORAGE (Cloudflare R2) ==========


STORAGES = {
    "default": {
        "BACKEND": "storages.backends.s3boto3.S3Boto3Storage",
    },
    "staticfiles": {
        "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage",
    },
}

AWS_ACCESS_KEY_ID = os.getenv("AWS_ACCESS_KEY_ID", "")
AWS_SECRET_ACCESS_KEY = os.getenv("AWS_SECRET_ACCESS_KEY", "")

AWS_STORAGE_BUCKET_NAME = "transsflow-media"

AWS_S3_ENDPOINT_URL = "https://2a8162f925f71a20a709d4dead129da9.r2.cloudflarestorage.com"
AWS_S3_REGION_NAME = "auto"
AWS_S3_SIGNATURE_VERSION = "s3v4"
AWS_S3_ADDRESSING_STYLE = "path"

AWS_DEFAULT_ACL = None
AWS_QUERYSTRING_AUTH = False  # Public files
AWS_S3_FILE_OVERWRITE = False
AWS_S3_VERIFY = True
AWS_S3_CUSTOM_DOMAIN = "pub-c701654ca9e940aca12af7f4bb0d66d6.r2.dev"
# Public delivery URL (NOT S3 endpoint)
MEDIA_URL = f"https://{AWS_S3_CUSTOM_DOMAIN}/"

LARK_WEBHOOKS = {
    "EHS": "https://open.larksuite.com/open-apis/bot/v2/hook/9189e378-1b8b-4292-b60f-d945e93c5e30",
    "IPQC": "https://open.larksuite.com/open-apis/bot/v2/hook/d7bcd5af-7068-4bc8-8a64-318126a05692",
}

# 🔥 Universal fallback group
LARK_DEFAULT_WEBHOOK = "https://open.larksuite.com/open-apis/bot/v2/hook/d7bcd5af-7068-4bc8-8a64-318126a05692"

TRANSS_FLOW_BUG_WEBHOOK = "https://open.larksuite.com/open-apis/bot/v2/hook/cf795d9a-fa5d-4cb0-96a7-764833564f5c"

# LOGGING CONFIGURATION
LOG_DIR = BASE_DIR / "log"
LOG_DIR.mkdir(parents=True, exist_ok=True)

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {
            "format": "[%(asctime)s] %(levelname)s [%(name)s:%(lineno)s] %(message)s",
            "datefmt": "%Y-%m-%d %H:%M:%S",
        },
    },
    "handlers": {
        "file": {
            "level": "WARNING",
            "class": "logging.FileHandler",
            "filename": LOG_DIR / "qms.log",
            "formatter": "verbose",
        },
        "console": {
            "level": "WARNING",
            "class": "logging.StreamHandler",
            "formatter": "verbose",
        },
    },
    "loggers": {
        "django": {
            "handlers": ["file", "console"],
            "level": "WARNING",
            "propagate": True,
        },
        "django.request": {
            "handlers": ["file", "console"],
            "level": "WARNING",
            "propagate": False,
        },
    },
    "root": {
        "handlers": ["file", "console"],
        "level": "WARNING",
    },
}