#!/usr/bin/env python
"""Django's command-line utility for administrative tasks."""
import os
import sys
from pathlib import Path

from decouple import config

BASE_DIR = Path(__file__).resolve().parent
APPS_DIR = BASE_DIR / 'apps'


def resolve_startapp_target(argv):
    """Make `python manage.py startapp <name>` create the app in apps/<name>.

    Django's startapp only creates the app in a subdirectory if that directory
    already exists and is passed as the second positional argument, so we
    create it and inject the path. Returns (app_name, target) when the app ends
    up under apps/, so its generated apps.py can be rewritten afterwards.
    """
    if len(argv) < 3 or argv[1] != 'startapp':
        return None

    positional = [a for a in argv[2:] if not a.startswith('-')]
    if not positional:
        return None

    app_name = positional[0]

    if len(positional) > 1:
        # A destination was given explicitly - honour it, but still fix up
        # apps.py if it lands inside apps/.
        target = Path(positional[1]).resolve()
    else:
        target = APPS_DIR / app_name
        if target.exists():
            raise SystemExit(f"CommandError: '{target}' already exists")
        target.mkdir(parents=True)
        argv.append(str(target))

    try:
        target.relative_to(APPS_DIR)
    except ValueError:
        return None
    return app_name, target


def fix_app_config(app_name, target):
    """Point the generated AppConfig at its real dotted path under apps/."""
    apps_py = target / 'apps.py'
    if not apps_py.exists():
        return

    dotted = '.'.join(('apps',) + target.relative_to(APPS_DIR).parts)
    source = apps_py.read_text(encoding='utf-8')
    for quote in ("'", '"'):
        source = source.replace(
            f'name = {quote}{app_name}{quote}',
            f'name = "{dotted}"',
        )
    apps_py.write_text(source, encoding='utf-8')
    print(f"Created app '{dotted}' - add '{dotted}' to LOCAL_APPS.")


def main():
    """Run administrative tasks."""
    os.environ.setdefault(
        'DJANGO_SETTINGS_MODULE',
        config('settings_module', default='config.settings.local'),
    )
    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        raise ImportError(
            "Couldn't import Django. Are you sure it's installed and "
            "available on your PYTHONPATH environment variable? Did you "
            "forget to activate a virtual environment?"
        ) from exc

    new_app = resolve_startapp_target(sys.argv)
    execute_from_command_line(sys.argv)
    if new_app:
        fix_app_config(*new_app)


if __name__ == '__main__':
    main()
