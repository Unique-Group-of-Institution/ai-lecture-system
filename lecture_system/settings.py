import os
from pathlib import Path

import dj_database_url
from django.core.exceptions import ImproperlyConfigured


BASE_DIR = Path(__file__).resolve().parent.parent


def required_environment(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise ImproperlyConfigured(f"Required environment variable {name} is not set")
    return value


def env_bool(name: str, default: bool = False) -> bool:
    return os.environ.get(name, str(default)).strip().lower() in {"1", "true", "yes", "on"}


def env_list(name: str) -> list[str]:
    return [item.strip() for item in os.environ.get(name, "").split(",") if item.strip()]


SECRET_KEY = required_environment("AI_LECTURE_SECRET_KEY")
DEBUG = env_bool("AI_LECTURE_DEBUG", default=True)
ALLOWED_HOSTS = env_list("AI_LECTURE_ALLOWED_HOSTS")
CSRF_TRUSTED_ORIGINS = env_list("AI_LECTURE_CSRF_TRUSTED_ORIGINS")

if os.environ.get("RAILWAY_ENVIRONMENT"):
    DEBUG = env_bool("AI_LECTURE_DEBUG", default=False)
    railway_public_domain = os.environ.get("RAILWAY_PUBLIC_DOMAIN", "").strip()
    if railway_public_domain and railway_public_domain not in ALLOWED_HOSTS:
        ALLOWED_HOSTS.append(railway_public_domain)
    if railway_public_domain:
        railway_origin = f"https://{railway_public_domain}"
        if railway_origin not in CSRF_TRUSTED_ORIGINS:
            CSRF_TRUSTED_ORIGINS.append(railway_origin)

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "lectures.apps.LecturesConfig",
    "ugi_sso.apps.UgiSsoConfig",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "lecture_system.urls"
TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    }
]
WSGI_APPLICATION = "lecture_system.wsgi.application"
ASGI_APPLICATION = "lecture_system.asgi.application"

DATABASE_URL = os.environ.get("DATABASE_URL", "").strip()
if DATABASE_URL:
    DATABASES = {
        "default": dj_database_url.config(
            default=DATABASE_URL,
            conn_max_age=600,
            conn_health_checks=True,
        )
    }
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": Path(os.environ.get("AI_LECTURE_SQLITE_PATH", BASE_DIR / "db.sqlite3")),
        }
    }

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "en-us"
TIME_ZONE = "Asia/Karachi"
USE_I18N = True
USE_TZ = True

STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_BACKEND = (
    "django.contrib.staticfiles.storage.StaticFilesStorage"
    if DEBUG
    else "whitenoise.storage.CompressedManifestStaticFilesStorage"
)
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": STATICFILES_BACKEND},
}
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

DATA_ROOT = Path(os.environ.get("AI_LECTURE_DATA_ROOT", BASE_DIR / "data"))
CONTENT_STORAGE_ROOT = Path(os.environ.get("AI_LECTURE_CONTENT_ROOT", DATA_ROOT / "content-library"))
CONTENT_MAX_UPLOAD_BYTES = int(os.environ.get("AI_LECTURE_CONTENT_MAX_BYTES", 25 * 1024 * 1024))
CONTENT_OCR_TIMEOUT_SECONDS = int(os.environ.get("AI_LECTURE_OCR_TIMEOUT_SECONDS", 120))
CONTENT_MAX_OCR_STDOUT_BYTES = int(os.environ.get("AI_LECTURE_MAX_OCR_STDOUT_BYTES", 8 * 1024 * 1024))
CONTENT_MAX_OCR_STDERR_BYTES = int(os.environ.get("AI_LECTURE_MAX_OCR_STDERR_BYTES", 256 * 1024))
CONTENT_RENDER_TIMEOUT_SECONDS = int(os.environ.get("AI_LECTURE_RENDER_TIMEOUT_SECONDS", 30))
CONTENT_PDF_TEXT_TIMEOUT_SECONDS = int(os.environ.get("AI_LECTURE_PDF_TEXT_TIMEOUT_SECONDS", 60))
CONTENT_PDF_INSPECTION_TIMEOUT_SECONDS = int(os.environ.get("AI_LECTURE_PDF_INSPECTION_TIMEOUT_SECONDS", 15))
CONTENT_MAX_PDF_INSPECTION_RESPONSE_BYTES = int(os.environ.get("AI_LECTURE_MAX_PDF_INSPECTION_RESPONSE_BYTES", 64 * 1024))
CONTENT_MAX_IMAGE_WIDTH = int(os.environ.get("AI_LECTURE_MAX_IMAGE_WIDTH", 10000))
CONTENT_MAX_IMAGE_HEIGHT = int(os.environ.get("AI_LECTURE_MAX_IMAGE_HEIGHT", 10000))
CONTENT_MAX_IMAGE_PIXELS = int(os.environ.get("AI_LECTURE_MAX_IMAGE_PIXELS", 40_000_000))
CONTENT_MAX_PDF_PAGES = int(os.environ.get("AI_LECTURE_MAX_PDF_PAGES", 300))
CONTENT_MAX_PDF_PAGE_WIDTH_POINTS = int(os.environ.get("AI_LECTURE_MAX_PDF_PAGE_WIDTH_POINTS", 14400))
CONTENT_MAX_PDF_PAGE_HEIGHT_POINTS = int(os.environ.get("AI_LECTURE_MAX_PDF_PAGE_HEIGHT_POINTS", 14400))
CONTENT_PDF_RENDER_SCALE = float(os.environ.get("AI_LECTURE_PDF_RENDER_SCALE", 2.0))
CONTENT_MAX_RENDERED_PAGE_PIXELS = int(os.environ.get("AI_LECTURE_MAX_RENDERED_PAGE_PIXELS", 25_000_000))
CONTENT_MAX_RENDERED_TOTAL_PIXELS = int(os.environ.get("AI_LECTURE_MAX_RENDERED_TOTAL_PIXELS", 75_000_000))
CONTENT_MAX_DERIVED_BYTES = int(os.environ.get("AI_LECTURE_MAX_DERIVED_BYTES", 100 * 1024 * 1024))
CONTENT_MAX_PAGE_TEXT_BYTES = int(os.environ.get("AI_LECTURE_MAX_PAGE_TEXT_BYTES", 5 * 1024 * 1024))
CONTENT_TESSERACT_PATH = Path(
    os.environ.get("AI_LECTURE_TESSERACT_PATH", DATA_ROOT / "content-tools" / "tesseract-5.4.0" / "tesseract.exe")
)
CONTENT_TESSDATA_PATH = Path(
    os.environ.get("AI_LECTURE_TESSDATA_PATH", DATA_ROOT / "content-tools" / "tesseract-5.4.0" / "tessdata")
)

GENERATION_MAX_SOURCES = int(os.environ.get("AI_LECTURE_GENERATION_MAX_SOURCES", 10))
GENERATION_MAX_TOTAL_CHARACTERS = int(os.environ.get("AI_LECTURE_GENERATION_MAX_CHARACTERS", 500_000))
GENERATION_MAX_PAGE_CHARACTERS = int(os.environ.get("AI_LECTURE_GENERATION_MAX_PAGE_CHARACTERS", 50_000))
GENERATION_MAX_PAGE_TEXT_BYTES = int(os.environ.get("AI_LECTURE_GENERATION_MAX_PAGE_BYTES", 200_000))
GENERATION_MAX_CLAIMS = int(os.environ.get("AI_LECTURE_GENERATION_MAX_CLAIMS", 120))
GENERATION_MAX_REQUEST_BYTES = int(os.environ.get("AI_LECTURE_GENERATION_MAX_REQUEST_BYTES", 256_000))

WORKFLOW_MAX_REQUEST_BYTES = int(os.environ.get("AI_LECTURE_WORKFLOW_MAX_REQUEST_BYTES", 64_000))
WORKFLOW_SQLITE_SINGLE_WORKER = DATABASES["default"]["ENGINE"].endswith("sqlite3")

RECORDING_STORAGE_ROOT = Path(os.environ.get("AI_LECTURE_RECORDING_ROOT", DATA_ROOT / "recordings"))
RECORDING_MAX_UPLOAD_BYTES = int(os.environ.get("AI_LECTURE_RECORDING_MAX_BYTES", 25 * 1024 * 1024))
RECORDING_MIN_DURATION_MS = int(os.environ.get("AI_LECTURE_RECORDING_MIN_DURATION_MS", 250))
RECORDING_MAX_DURATION_MS = int(os.environ.get("AI_LECTURE_RECORDING_MAX_DURATION_MS", 20 * 60 * 1000))
RECORDING_MAX_REQUEST_BYTES = RECORDING_MAX_UPLOAD_BYTES + 64 * 1024

# Dedicated cross-service secret. Never reuse Django SECRET_KEY.
UGI_CRM_SSO_SIGNING_SECRET = os.environ.get("UGI_CRM_SSO_SIGNING_SECRET", "").strip()

# HTTPS security defaults for remote deployment. Railway terminates TLS at its proxy.
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SESSION_COOKIE_SECURE = env_bool("AI_LECTURE_SECURE_COOKIES", default=not DEBUG)
CSRF_COOKIE_SECURE = env_bool("AI_LECTURE_SECURE_COOKIES", default=not DEBUG)

# T050 renders only through a server-side local adapter into ignored project
# storage. Enabling it requires an explicit process-only evaluation acknowledgement.
VIDEO_STORAGE_ROOT = DATA_ROOT / "lectures" / "t050-video"
VIDEO_EXPORT_ROOT = DATA_ROOT / "exports" / "t050-video"
REMOTION_PROJECT_ROOT = BASE_DIR / "remotion"
VIDEO_RENDER_ADAPTER_ENABLED = os.environ.get("AI_LECTURE_VIDEO_RENDER_ADAPTER", "") == "1"
VIDEO_RENDER_EVALUATION_ACK = (
    os.environ.get("AI_LECTURE_REMOTION_EVALUATION_ACK", "") == "evaluation-only-2026-08-20"
)
VIDEO_RENDER_DEPLOYMENT_MODE = os.environ.get("AI_LECTURE_DEPLOYMENT_MODE", "").strip().lower()
VIDEO_RENDER_EXECUTION_HOST = os.environ.get("AI_LECTURE_LOCAL_EXECUTION_HOST", "").strip().lower()
VIDEO_RENDER_RAILWAY_ENVIRONMENT = bool(os.environ.get("RAILWAY_ENVIRONMENT", "").strip())
VIDEO_RENDER_TIMEOUT_SECONDS = 3600
VIDEO_RENDER_MAX_OUTPUT_BYTES = 2 * 1024 * 1024 * 1024
VIDEO_RENDER_MAX_REQUEST_BYTES = 64 * 1024

# FINAL-03: controlled Django -> Node slide-engine boundary.
SLIDE_ENGINE_ROOT = BASE_DIR / "slide-engine"
SLIDE_ENGINE_EXECUTABLE = os.environ.get("AI_LECTURE_NODE_EXECUTABLE", "node").strip() or "node"
SLIDE_ENGINE_TIMEOUT_SECONDS = int(os.environ.get("AI_LECTURE_SLIDE_ENGINE_TIMEOUT_SECONDS", 180))
SLIDE_ENGINE_MAX_STDOUT_BYTES = int(os.environ.get("AI_LECTURE_SLIDE_ENGINE_MAX_STDOUT_BYTES", 64 * 1024))
SLIDE_ENGINE_MAX_STDERR_BYTES = int(os.environ.get("AI_LECTURE_SLIDE_ENGINE_MAX_STDERR_BYTES", 256 * 1024))
SLIDE_ENGINE_MAX_PPTX_BYTES = int(os.environ.get("AI_LECTURE_SLIDE_ENGINE_MAX_PPTX_BYTES", 50 * 1024 * 1024))
SLIDE_ENGINE_STORAGE_ROOT = DATA_ROOT / "slide-engine"

LOGIN_URL = "/accounts/login/"
LOGIN_REDIRECT_URL = "/teacher/recordings/"
