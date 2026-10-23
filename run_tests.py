"""Run the Django test suite with service-free test settings."""

import os
import sys

from django.core.management import execute_from_command_line


os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.test")
execute_from_command_line(["manage.py", "test", *sys.argv[1:]])