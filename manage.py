#!/usr/bin/env python
import os
import sys
import argparse

from ipydex import IPS, activate_ips_on_exception

if os.environ.get("CI") != "true":
    activate_ips_on_exception()

if __name__ == "__main__":

    os.environ["DJANGO_SETTINGS_MODULE"] = "ackrep_core_django_settings.settings"

    # enable to pass custom options to unittests
    # source: https://stackoverflow.com/a/43878837/333403
    argv = sys.argv
    cmd = argv[1] if len(argv) > 1 else None
    if cmd in ["test"]:  # limit the extra arguments to certain commands
        parser = argparse.ArgumentParser(add_help=False)
        parser.add_argument("--include-slow", action="store_true")
        args, argv = parser.parse_known_args(argv)
        # We can save the argument as an environmental variable, in
        # which case it's to retrieve from within `project.settings`,
        os.environ["DJANGO_TESTS_INCLUDE_SLOW"] = str(args.include_slow)
        sys.argv = argv

    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        raise ImportError(
            "Couldn't import Django. Are you sure it's installed and "
            "available on your PYTHONPATH environment variable? Did you "
            "forget to activate a virtual environment?"
        ) from exc
    execute_from_command_line(argv)
