from colorama import Style, Fore
from django.utils import timezone

import os
from ipydex import Container


# path of this module (i.e. the file core.py)
mod_path = os.path.dirname(os.path.abspath(__file__))

# path of this package (i.e. the directory ackrep_core)
core_pkg_path = os.path.dirname(mod_path)

# path of the general project root (expected to contain ackrep_data, ackrep_core, ackrep_deployment, ...)
root_path = os.path.abspath(os.path.join(mod_path, "..", ".."))

# paths for (ackrep_data and its test-related clone)
data_path = os.path.join(root_path, "ackrep_data")
data_test_repo_path = os.path.join(root_path, "ackrep_data_for_unittests")


class ResultContainer(Container):
    """
    @DynamicAttrs
    """

    pass


class ObjectContainer(Container):
    """
    @DynamicAttrs
    """

    pass


class InconsistentMetaDataError(ValueError):
    """Raised when an entity with inconsistent metadata is loaded."""

    pass


class DuplicateKeyError(Exception):
    """Raised when a duplicate key is found in the database."""

    def __init__(self, dup_key):
        super().__init__(f"Duplicate key in database '{dup_key}'")


class QueryError(Exception):
    pass

def bright(txt):
    return f"{Style.BRIGHT}{txt}{Style.RESET_ALL}"


def bgreen(txt):
    return f"{Fore.GREEN}{Style.BRIGHT}{txt}{Style.RESET_ALL}"


def bred(txt):
    return f"{Fore.RED}{Style.BRIGHT}{txt}{Style.RESET_ALL}"


def yellow(txt):
    return f"{Fore.YELLOW}{txt}{Style.RESET_ALL}"


# based on
# source: https://stackoverflow.com/a/46928226/333403
# by chidimo
def smooth_timedelta(start_datetime, end_datetime=None):
    """Convert a datetime.timedelta object into Days, Hours, Minutes, Seconds."""
    if end_datetime is None:
        end_datetime = timezone.now()
    timedeltaobj = end_datetime - start_datetime
    secs = timedeltaobj.total_seconds()
    timetot = ""
    if secs > 86400:  # 60sec * 60min * 24hrs
        days = secs // 86400
        timetot += "{}d".format(int(days))
        secs = secs - days * 86400

    if secs > 3600:
        hrs = secs // 3600
        timetot += " {}h".format(int(hrs))
        secs = secs - hrs * 3600

    if secs > 60:
        mins = secs // 60
        timetot += " {}m".format(int(mins))
        secs = secs - mins * 60

    if secs > 0:
        timetot += " {}s".format(int(secs))
    return timetot
