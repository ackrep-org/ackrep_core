#!/usr/bin/env python
import os
import sys

from ipydex import IPS, activate_ips_on_exception
activate_ips_on_exception()

if __name__ == '__main__':

    #mod_path = os.path.dirname(os.path.abspath(__file__))

    # sys.path.insert(0, os.path.join(mod_path, "ackrep_core"))
    # os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'django_settings.settings')

    # os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'settings.settings')
    os.environ['DJANGO_SETTINGS_MODULE'] = 'ackrep_core_django_settings.settings'

    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        raise ImportError(
            "Couldn't import Django. Are you sure it's installed and "
            "available on your PYTHONPATH environment variable? Did you "
            "forget to activate a virtual environment?"
        ) from exc
    execute_from_command_line(sys.argv)
