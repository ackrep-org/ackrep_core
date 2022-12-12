"""
This module serves as dispatcher to other modules.
Rationale:importing this module is fast, but it allows easy access to many other modules, which will be imported
only if actually needed. This reduces the startup time e.g. of invocations of script.py.
"""

# the following is to enable IDE autocompletion without actually importing modules

# noinspection PyUnreachableCode
if 0:
    # noinspection PyUnresolvedReferences
    from ackrep_core import (
        core,
        ackrep_parser,
        automatic_model_creation,
        config_handler,
        logging,
        model_utils,
        models,
        release,
        system_model_management,
        util,
    )


# use a dict here for fast lookup
KNOWN_MODULES = {
    "ackrep_parser": 1,
    "automatic_model_creation": 1,
    "config_handler": 1,
    "core": 1,
    "logging": 1,
    "model_utils": 1,
    "models": 1,
    "modules": 1,
    "release": 1,
    "system_model_management": 1,
    "util": 1,
    }


def __getattr__(name: str):
    """
    import and return modules when they are needed (but not earlier)

    :param name:    module nam
    :return:        imported module
    """

    # first handle special cases of external modules:

    if name == "settings":
        from django.conf import settings
        return settings

    if name not in KNOWN_MODULES:
        msg = f"unknown module name: {name}"
        raise NameError(msg)

    import importlib
    mod = importlib.import_module(f"ackrep_core.{name}")
    return mod
