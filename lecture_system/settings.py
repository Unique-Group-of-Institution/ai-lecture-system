import os
from pathlib import Path

from django.core.exceptions import ImproperlyConfigured


BASE_DIR = Path(__file__).resolve().parent.parent


def required_environment(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise ImproperlyConfigured(f"Required environment variable {name} is not set")
    return value


SECRET_KEY = required_environment("AI_LECTURE_SECRET_KEY")
DEBUG = True
ALLOWED_HOSTS: list[str] = []

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "lectures.apps.LecturesConfig",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
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
STATIC_URL = "static/"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

CONTENT_STORAGE_ROOT = Path(os.environ.get("AI_LECTURE_CONTENT_ROOT", BASE_DIR / "data" / "content-library"))
CONTENT_MAX_UPLOAD_BYTES = int(os.environ.get("AI_LECTURE_CONTENT_MAX_BYTES", 25 * 1024 * 1024))
CONTENT_OCR_TIMEOUT_SECONDS = int(os.environ.get("AI_LECTURE_OCR_TIMEOUT_SECONDS", 120))
CONTENT_TESSERACT_PATH = Path(
    os.environ.get("AI_LECTURE_TESSERACT_PATH", BASE_DIR / "data" / "content-tools" / "tesseract-5.4.0" / "tesseract.exe")
)
CONTENT_TESSDATA_PATH = Path(
    os.environ.get("AI_LECTURE_TESSDATA_PATH", BASE_DIR / "data" / "content-tools" / "tesseract-5.4.0" / "tessdata")
)
