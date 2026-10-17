#!/bin/sh
# Dev: apply migrations, then the dev server.
set -e

export settings_module=config.settings.dev

python manage.py migrate --noinput
exec python manage.py runserver 0.0.0.0:8000
