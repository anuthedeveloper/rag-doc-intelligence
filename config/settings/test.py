"""Settings for running the test suite without external services."""

from .base import *  # noqa: F401,F403

DEBUG = False
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": ":memory:",
    }
}

# Tests mock task and provider boundaries; no broker is required.
CELERY_TASK_ALWAYS_EAGER = True
CELERY_TASK_EAGER_PROPAGATES = True
MEDIA_ROOT = BASE_DIR / ".test-media"
MIGRATION_MODULES = {
    "documents": None,
    "retrieval": None,
}