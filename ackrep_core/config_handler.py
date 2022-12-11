import os
import appdirs
from colorama import Style, Fore

from ackrep_core import logging

try:
    # this will be part of standard library for python >= 3.11
    import tomllib
except ModuleNotFoundError:
    import tomli as tomllib

APPNAME = "ackrep"
DEFAULT_CONFIGFILE_PATH = os.path.join(appdirs.user_config_dir(appname=APPNAME), "ackrepconf.toml")


def bootstrap_config_from_current_directory(configfile_path=None):
    """
    Try to load configfile. If it does not exist: create. Anyway: check

    :param configfile_path:     path to where the config file should be located (optional)
    """

    # use cwd as ackrep root (parent of ackrep_core, ackrep_data, etc)
    # then expect erk/erkdata/... as "sibling"

    configfile_path = DEFAULT_CONFIGFILE_PATH

    if not os.path.isfile(configfile_path):
        # create new config file
        _create_new_config_file(configfile_path)
        # call this function again to perform the check
        print_flag = True
        msg = ""
    else:
        msg = f"{configfile_path} does already exist. Nothing done."
        print_flag = False

    try:
        load_config_file(configfile_path, print_flag=print_flag)
    except tomllib.TOMLDecodeError as ex:
        errmsg = f"Error while decoding {configfile_path}: {ex.args}"
        raise tomllib.TOMLDecodeError(errmsg)
    else:
        if msg:
            logging.logger.info(msg)

    return configfile_path


def _create_new_config_file(configfile_path):

    # for performance reasons: do some imports here on function level
    from textwrap import dedent as twdd
    from pathlib import Path

    if os.path.isfile(configfile_path):
        raise FileExistsError(configfile_path)

    containing_dir = os.path.split(configfile_path)[0]
    os.makedirs(containing_dir, exist_ok=True)

    # assuming the directory structure:
    #
    # <common-root>
    # │
    # ├── ackrep
    # │   ├── ackrep_data/    ← assume this (or a sibling) to be your current working directory
    # │   │
    # │   └── ...
    # └── erk
    #     └── erk-data/

    path1 = Path.cwd().parent.parent.joinpath("erk", "erk-data", "ocse", "erkpackage.toml").as_posix()

    default_configfile_content = twdd(f"""

    ERK_DATA_OCSE_CONF_ABSPATH = "{path1}"
    """)

    with open(configfile_path, "w", encoding="utf8") as txtfile:
        txtfile.write(default_configfile_content)

    str1 = "file created: "
    logging.logger.info(f'{str1:<30}{configfile_path} {bgreen("✓")}')


def load_config_file(configfile_path: str = None, check=True, print_flag=False) -> dict:

    # load config file
    # this will raise an error if the toml syntax is not correct

    if configfile_path is None:
        configfile_path = DEFAULT_CONFIGFILE_PATH

    with open(configfile_path, "rb") as fp:
        config_dict = tomllib.load(fp)

    if not isinstance(config_dict, dict):

        msg = (
            f"Expected dict but got {type(config_dict)}. "
            f"Perhaps wrong yaml syntax in {configfile_path}."
        )
        raise TypeError(msg)
    # this will raise an error if the relevant keys are missing

    if check:
        relevant_keys = ["ERK_DATA_OCSE_CONF_ABSPATH"]
        missing_keys = [key for key in relevant_keys if key not in config_dict]

        if missing_keys:
            missing_keys_str = "\n- ".join(missing_keys)
            msg = f"The following keys are missing in {configfile_path}:" f"{missing_keys_str}\n."
            raise KeyError(msg)

    if print_flag:
        str1 = "config file check passed: "
        logging.logger.info(f'{str1:<30}{configfile_path} {bgreen("✓")}')

    return config_dict

def bgreen(txt):
    return f"{Fore.GREEN}{Style.BRIGHT}{txt}{Style.RESET_ALL}"
