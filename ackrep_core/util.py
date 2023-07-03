import os
from ackrep_core import logging
from colorama import Style, Fore
from django.utils import timezone
import yaml
import subprocess
from git import Repo
import functools
from threading import Thread

from ipydex import Container

# TODO: do we need these paths here?
# path of this module (i.e. the file core.py)
mod_path = os.path.dirname(os.path.abspath(__file__))

# path of this package (i.e. the directory ackrep_core)
# (this is where manage.py is located)
core_pkg_path = os.path.dirname(mod_path)


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
        super().__init__(f"Duplicate key in database: '{dup_key}'")


class QueryError(Exception):
    pass


class DockerError(Exception):
    pass


def bright(txt):
    return f"{Style.BRIGHT}{txt}{Style.RESET_ALL}"


def bgreen(txt):
    return f"{Fore.GREEN}{Style.BRIGHT}{txt}{Style.RESET_ALL}"


def bred(txt):
    return f"{Fore.RED}{Style.BRIGHT}{txt}{Style.RESET_ALL}"


def yellow(txt):
    return f"{Fore.YELLOW}{txt}{Style.RESET_ALL}"


def smart_parse(obj):
    """
    Due to simplified database representation entity.tag_list, sometimes is not a list but a string.
    In these cases the string must be parsed to a list.

    :param obj:
    :return:
    """

    if isinstance(obj, list):
        return obj
    else:
        return yaml.load(obj, Loader=yaml.SafeLoader)


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


def utf8decode(obj):
    if hasattr(obj, "decode"):
        return obj.decode("utf8")
    else:
        return obj


def strip_decode(obj) -> str:

    # get rid of some (ipython-related boilerplate bytes (ended by \x07))
    if hasattr(obj, "split"):
        delim = b"\x07"
        obj = obj.split(delim)[-1]
    return utf8decode(obj)


def run_command(arglist, logger=None, capture_output=True, **kwargs):
    """
    Unified handling of calling commands.
    Automatically prints an error message if necessary.
    """
    res = subprocess.run(arglist, capture_output=capture_output, **kwargs)
    res.exited = res.returncode
    res.stdout = strip_decode(res.stdout)
    res.stderr = strip_decode(res.stderr)
    if res.returncode != 0:
        msg = f"""
        The command `{' '.join(arglist)}` exited with returncode {res.returncode}.

        stdout: {res.stdout}

        stderr: {res.stderr}
        """
        if isinstance(logger, logging.logging.Logger):
            logger.error(msg)

    return res


def git_push(repo_path: str, files_to_add, message: str):
    repo = Repo(repo_path)
    repo.git.add(files_to_add)
    repo.index.commit(message)
    origin = repo.remote(name="origin")
    origin.push()


def find_nth(haystack, needle, n):
    """string search: find position of nth occurence of "needle" in "haystack" """
    start = haystack.find(needle)
    while start >= 0 and n > 1:
        start = haystack.find(needle, start + len(needle))
        n -= 1
    return start


def timeout_handler(signum, frame):
    raise TimeoutError(f"Process reached max time and was therefore canceled.")


class TimeoutException(Exception):
    pass


# source of decorator for the timeout:
# https://stackoverflow.com/questions/21827874/timeout-a-function-windows


def timeout(timeout):
    def deco(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            res = [TimeoutException("function [%s] timeout [%s seconds] exceeded!" % (func.__name__, timeout))]

            def newFunc():
                try:
                    res[0] = func(*args, **kwargs)
                except Exception as e:
                    res[0] = e

            t = Thread(target=newFunc)
            t.daemon = True
            try:
                t.start()
                t.join(timeout)
            except Exception as je:
                print("error starting thread")
                raise je
            ret = res[0]
            if isinstance(ret, BaseException):
                raise ret
            return ret

        return wrapper

    return deco
