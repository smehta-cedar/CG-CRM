#!/bin/sh
# Prod: apply migrations, collect static files, then gunicorn
# (settings in config/gunicorn.py).
set -e

export settings_module=config.settings.prod

# gunicorn opens its log files before Django creates logs/.
mkdir -p logs

# Anything printed to stderr (a crash before logging is set up, a failed
# migrate, a print) lands in the raw error log too.
exec 2>>logs/error-raw.log

python manage.py migrate --noinput
python manage.py collectstatic --noinput -v 0

exec gunicorn -c config/gunicorn.py config.wsgi:application
