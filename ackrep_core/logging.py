"""
This module serves to keep logging functionality separated from .core.

"""
import os
import sys
import logging  # logging module from python std lib



defaul_loglevel = os.environ.get("ACKREP_LOG_LEVEL", logging.INFO)
FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
logging.basicConfig(
    level=defaul_loglevel,
    format = FORMAT,
    handlers=[
        # lg.FileHandler("ackrep.log"),
        logging.StreamHandler(sys.stdout)
    ]
)


logger = logging.getLogger("ackrep_logger")

# initialize logging with default loglevel (might be overwritten by command line option)
# see https://docs.python.org/3/howto/logging-cookbook.html
DATEFORMAT = "%H:%M:%S"
formatter = logging.Formatter(fmt=FORMAT, datefmt=DATEFORMAT)
handler = logging.StreamHandler(sys.stdout)
handler.setFormatter(formatter)
logger.addHandler(handler)
logger.setLevel(defaul_loglevel)


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
