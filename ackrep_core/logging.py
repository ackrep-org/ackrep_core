"""
This module serves to keep logging functionality separated from .core.

"""
import os
import sys
import logging  # logging module from python std lib


# initialize logging with default loglevel (might be overwritten by command line option)
# see https://docs.python.org/3/howto/logging-cookbook.html

defaul_loglevel = os.environ.get("ACKREP_LOG_LEVEL", logging.INFO)
FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
DATEFORMAT = "%H:%M:%S"
logging.basicConfig(
    level=defaul_loglevel,
    format=FORMAT,
    datefmt=DATEFORMAT,
    handlers=[
        # lg.FileHandler("ackrep.log"),
        logging.StreamHandler(sys.stdout)
    ],
)


logger = logging.getLogger("ackrep")


def send_debug_report(send=None):
    """
    Send debug information such as relevant environmental variables to designated output (logger or stdout).

    :param send:    Function to be used for sending the message. Default: logger.debug. Alternatively: print.
    """

    if send is None:
        send = logger.debug

    row_template = "  {:<30}: {}"

    send("** ENVIRONMENT VARS: **")
    for k, v in os.environ.items():
        if k.startswith("ACKREP_"):
            send(row_template.format(k, v))

    # send("** DB CONNECTION:  **")
    # from django.db import connection as django_db_connection, connections as django_db_connections
    # send(django_db_connections["default"].get_connection_params())
    send("\n")
