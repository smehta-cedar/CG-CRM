#!/bin/sh
# Local: dev server with auto-reload.
set -e

export settings_module=config.settings.local

exec python manage.py runserver 0.0.0.0:8000
