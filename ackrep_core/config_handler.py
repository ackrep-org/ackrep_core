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
    # CAUTION: beware the underscores and dashes
    #
    # <common-root>
    # │
    # ├── ackrep              ← assume this to be your current working directory
    # │   ├── ackrep_data/
    # │   │
    # │   └── ...
    # └── erk
    # │   ├── erk_data/
    # │   ├── erk_data_for_unittests/
    #     └── ...

    cwd = Path.cwd().as_posix()
    ackrep_root_path = Path.cwd().as_posix()
    ocse_path = Path.cwd().parent.joinpath("erk", "erk_data", "ocse", "erkpackage.toml").as_posix()
    ocse_ut_path = Path.cwd().parent.joinpath("erk", "erk_data_for_unittests", "ocse", "erkpackage.toml").as_posix()
    ackrep_data_path = os.path.join(ackrep_root_path, "ackrep_data")

    check_paths = [
        ("ACKREP_ROOT_PATH", ackrep_root_path),
        ("ERK_DATA_OCSE_CONF_PATH", ocse_path),
        ("ERK_DATA_OCSE_UT_CONF_PATH", ocse_ut_path),
        ("ACKREP_DATA_PATH", ackrep_data_path),
    ]

    if os.path.split(cwd)[-1] != "ackrep":
        msg = f"The current workdir is not `ackrep` (as expected) but instead {cwd}."
        logging.logger.warn(msg)

    for name, pathstr in check_paths:
        if not os.path.exists(pathstr):
            msg = (
                f"Unexpectedly did not find path `{pathstr}` ({name}) "
                f"This failing safety check means that your working dir ({cwd}) is probably wrong (or still incomplete). "
                "Proceeding anyway."
            )
            logging.logger.warn(msg)

    #
    if os.environ.get("ACKREP_CORE_UT") == "True":
        ocse_path = ocse_ut_path
        logging.logger.warn("inside CI there is no ERK_DATA, for compatibility, we point ERK_DATA at ERK_DATA_UT")
    if os.environ.get("ACKREP_DATA_UT") == "True":
        ocse_ut_path = ocse_path
        logging.logger.warn("inside CI there is no ERK_DATA_UT, for compatibility, we point ERK_DATA_UT at ERK_DATA")

    default_configfile_content = twdd(
        f"""

    ACKREP_ROOT_PATH = "{ackrep_root_path}"
    ERK_DATA_OCSE_CONF_PATH = "{ocse_path}"
    ERK_DATA_OCSE_UT_CONF_PATH = "{ocse_ut_path}"
    """
    )

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

        msg = f"Expected dict but got {type(config_dict)}. " f"Perhaps wrong yaml syntax in {configfile_path}."
        raise TypeError(msg)
    # this will raise an error if the relevant keys are missing

    if check:
        relevant_keys = ["ERK_DATA_OCSE_CONF_PATH"]
        missing_keys = [key for key in relevant_keys if key not in config_dict]

        if missing_keys:
            missing_keys_str = "\n- ".join(missing_keys)
            msg = f"The following keys are missing in {configfile_path}:" f"{missing_keys_str}\n."
            raise KeyError(msg)

    if print_flag:
        str1 = "config file check passed: "
        logging.logger.info(f'{str1:<30}{configfile_path} {bgreen("✓")}')

    return config_dict


class FlexibleConfigHandler(object):
    """
    This singleton class provides access to config data if available and gives reasonable error messages if not
    """

    is_initialized = False

    def __new__(cls):
        if not hasattr(cls, "instance"):
            cls.instance = super().__new__(cls)
        return cls.instance

    def __init__(self):

        # prevent multiple calls
        if self.is_initialized:
            return

        try:
            self.config_dict = load_config_file()
            self.config_file_found = True
        except FileNotFoundError:
            self.config_dict = {}
            self.config_file_found = False

            # this is currently the best option as it provides a better error message than just leaving the dict empty
            raise

        self.define_paths()
        self.instance = self
        self.is_initialized = True

    # noinspection PyAttributeOutsideInit
    def define_paths(self):
        """
        Define some important paths either based on the config file or based on envvars
        :return:
        """

        if ackrep_root_path := os.environ.get("ACKREP_ROOT_PATH"):
            self.ACKREP_ROOT_PATH = ackrep_root_path
        elif ackrep_root_path := self.config_dict.get("ACKREP_ROOT_PATH"):
            self.ACKREP_ROOT_PATH = ackrep_root_path

        # ackrep_data (which might be different for unittests)
        # this env-variable will be set e.g. by unit tests to make cli invocations from tests work
        if ackrep_data_path := os.environ.get("ACKREP_DATA_PATH"):
            self.ACKREP_DATA_PATH = ackrep_data_path
        elif ackrep_data_path := self.config_dict.get("ACKREP_DATA_PATH"):
            self.ACKREP_DATA_PATH = ackrep_data_path
        elif ackrep_root_path:
            self.ACKREP_DATA_PATH = os.path.join(self.ACKREP_ROOT_PATH, "ackrep_data")

        # ackrep_ci_results (which might also be different for unitests)
        # this env-variable will be set e.g. by unit tests to make cli invocations from tests work
        if ackrep_ci_result_path := os.environ.get("ACKREP_CI_RESULTS_PATH"):
            self.ACKREP_CI_RESULTS_PATH = ackrep_ci_result_path
        elif ackrep_ci_result_path := self.config_dict.get("ACKREP_CI_RESULTS_PATH"):
            self.ACKREP_CI_RESULTS_PATH = ackrep_ci_result_path
        elif ackrep_root_path:
            self.ACKREP_CI_RESULTS_PATH = os.path.join(self.ACKREP_ROOT_PATH, "ackrep_ci_results")

        # database paths with hardcoded filenames
        self.ACKREP_UT_DATABASE_PATH = os.path.join(ackrep_root_path, "ackrep_core", "db_for_unittests.sqlite3")

        if os.environ.get("ACKREP_DATABASE_PATH"):
            self.ACKREP_DATABASE_PATH = os.environ.get("ACKREP_DATABASE_PATH")
        elif os.environ.get("ACKREP_UNITTEST") == "True":
            self.ACKREP_DATABASE_PATH = self.ACKREP_UT_DATABASE_PATH
        else:
            self.ACKREP_DATABASE_PATH = os.path.join(ackrep_root_path, "ackrep_core", "db.sqlite3")

        if ocse_conf_path := self._get_ocse_conf_path("ERK_DATA_OCSE_MAIN_PATH"):
            os.environ["PYERK_CONF_PATH"] = ocse_conf_path

    def _get_ocse_conf_path(self, name) -> str:

        # note the difference between ..._MAIN_... and ..._CONF_...
        # TODO: explain this difference in comments or docs

        if name == "ERK_DATA_OCSE_MAIN_PATH":
            if os.environ.get("ACKREP_UNITTEST") == "True":
                ocse_conf_path = self.ERK_DATA_OCSE_UT_CONF_PATH
            else:
                ocse_conf_path = self.ERK_DATA_OCSE_CONF_PATH

        if name == "ERK_DATA_OCSE_UT_MAIN_PATH":
            ocse_conf_path = self.ERK_DATA_OCSE_UT_CONF_PATH
        return ocse_conf_path

    def __getattr__(self, name):

        from pathlib import Path

        # this is necessary to make that class working with djangos settings-wrapping
        if name == "_mask_wrapped":
            raise AttributeError

        if not self.config_file_found:
            msg = (
                f"ackrep config file {DEFAULT_CONFIGFILE_PATH} could not be found; "
                f"Thus, {name} is not available. Maybe you have to run `ackrep --bootstrap-config`?"
            )
            raise FileNotFoundError(msg)

        # handle some special cases
        if name in ["ERK_DATA_OCSE_MAIN_PATH", "ERK_DATA_OCSE_UT_MAIN_PATH"]:
            ocse_conf_path = self._get_ocse_conf_path(name)

            if not os.path.isfile(ocse_conf_path):
                msg = f"Error on loading OCSE config file: {ocse_conf_path}"
                raise FileNotFoundError(msg)

            with open(ocse_conf_path, "rb") as fp:
                erk_conf_dict = tomllib.load(fp)

            ocse_main_rel_path = erk_conf_dict["main_module"]
            ocse_main_mod_path = Path(ocse_conf_path).parent.joinpath(ocse_main_rel_path).as_posix()
            return ocse_main_mod_path

        # handle the general case
        return self.config_dict[name]


def bgreen(txt):
    return f"{Fore.GREEN}{Style.BRIGHT}{txt}{Style.RESET_ALL}"
