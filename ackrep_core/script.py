import argparse
import subprocess
import pprint
import time
import datetime
import questionary
import platform
from django.core import management
from django.conf import settings
import yaml

from ipydex import IPS, activate_ips_on_exception

from ackrep_core import system_model_management

from ackrep_core import release

activate_ips_on_exception()

from . import core
from . import models
from .util import *


def main():
    argparser = argparse.ArgumentParser()
    argparser.add_argument("--version", help="version of the ackrep_core framework", action="store_true")
    argparser.add_argument("--key", help="print a random key and exit", action="store_true")
    argparser.add_argument(
        "-c",
        "--check",
        metavar="metadatafile",
        help="check solution or system model (specified by path to metadata file or key)"
        + "using the locally installed packages",
    )
    argparser.add_argument(
        "-cwd",
        "--check-with-docker",
        metavar="metadatafile",
        help="check solution or system model (specified by path to metadata file or key)"
        + "using correct environment specification (docker)",
    )
    argparser.add_argument(
        "--check-all-solutions", help="check all solutions (may take some time)", action="store_true"
    )
    argparser.add_argument(
        "--check-all-system-models", help="check all system models (may take some time)", action="store_true"
    )
    argparser.add_argument(
        "--test-ci", help="check some entities, some will fail", action="store_true"
    )
    argparser.add_argument(
        "--update-parameter-tex",
        metavar="metadatafile",
        help="update parameters of system model in tex file (system model entity is specified by metadata file or key)",
    )
    argparser.add_argument(
        "--create-pdf",
        metavar="metadatafile",
        help="create pdf of system model from tex file (system model entity is specified by metadata file or key)",
    )
    argparser.add_argument(
        "--create-system-model-list-pdf",
        help="create pdf of all known system models, stored in <project_dir>/local_outputs/",
        action="store_true",
    )
    argparser.add_argument(
        "--get-metadata-abs-path-from-key", metavar="key", help="return absolute path to metadata file for a given key"
    )
    argparser.add_argument(
        "--get-metadata-rel-path-from-key",
        metavar="key",
        help="return path to metadata file (relative to repo root) for a given key",
    )
    argparser.add_argument("--bootstrap-db", help="delete database and recreate it (without data)", action="store_true")
    argparser.add_argument(
        "--bootstrap-test-db", help="delete database for unittests and recreate it (without data)", action="store_true"
    )
    argparser.add_argument("--start-workers", help="start the celery workers", action="store_true")
    argparser.add_argument(
        "--prepare-script",
        help="render the execscript and place it in the docker transfer folder (specified by path to metadata file or key)",
        metavar="metadatafile",
    )
    argparser.add_argument(
        "-rie",
        "--run-interactive-environment",
        nargs="+",
        help="Start an interactive session with a docker container of an environment image of your choice."
        + "Environment key must be specified. Additional arguments ('a; b; c') for inside the env are optional.",
        metavar="key",
    )
    argparser.add_argument("-n", "--new", help="interactively create new entity", action="store_true")
    argparser.add_argument("-l", "--load-repo-to-db", help="load repo to database", metavar="path")
    argparser.add_argument("-e", "--extend", help="extend database with repo", metavar="path")
    argparser.add_argument("--qq", help="create new metada.yml based on interactive questionnaire", action="store_true")

    # for development only
    argparser.add_argument("--dd", help="start interactive IPython shell for debugging", action="store_true")
    argparser.add_argument("--md", help="shortcut for `-m metadata.yml`", action="store_true")
    argparser.add_argument("-m", "--metadata", help="process metadata in yaml syntax (.yml file). ")
    argparser.add_argument(
        "--show-debug", help="set exitflags false in order to see underlying debug outputs", action="store_true"
    )

    argparser.add_argument("--show-entity-info", metavar="key", help="print out some info about the entity")

    argparser.add_argument(
        "--log", metavar="loglevel", help="specify log level: DEBUG (10), INFO, WARNING, ERROR, CRITICAL (50)", type=int
    )

    argparser.add_argument(
        "--test-logging", help="print out some dummy messages for each logging category", action="store_true"
    )

    args = argparser.parse_args()

    # non-exclusive options
    if args.log:
        core.logger.setLevel(int(args.log))

    if os.environ.get("ACKREP_PRINT_DEBUG_REPORT"):
        core.send_debug_report(print)
    else:
        # default: use logger.debug
        core.send_debug_report(core.logger.debug)

    # exclusive options
    if args.new:
        create_new_entity()
    elif args.dd:
        IPS()
    elif args.load_repo_to_db:
        startdir = args.load_repo_to_db
        core.load_repo_to_db(startdir)
        print(bgreen("Done"))
    elif args.extend:
        startdir = args.extend
        core.extend_db(startdir)
        print(bgreen("Done"))
    elif args.qq:

        entity = dialoge_entity_type()
        field_values = dialoge_field_values(entity)
        core.convert_dict_to_yaml(field_values, target_path="./metadata.yml")
        return
    elif args.check:
        metadatapath = args.check
        check(metadatapath)
    elif args.check_with_docker:
        metadatapath = args.check_with_docker
        check_with_docker(metadatapath)
    elif args.check_all_solutions:
        check_all_solutions()
    elif args.check_all_system_models:
        check_all_system_models()
    elif args.test_ci:
        test_ci()
    elif args.get_metadata_abs_path_from_key:
        key = args.get_metadata_abs_path_from_key
        exitflag = not args.show_debug
        get_metadata_path_from_key(key, absflag=True, exitflag=exitflag)
    elif args.get_metadata_rel_path_from_key:
        key = args.get_metadata_rel_path_from_key
        exitflag = not args.show_debug
        get_metadata_path_from_key(key, absflag=False, exitflag=exitflag)
    elif args.update_parameter_tex:
        metadatapath = args.update_parameter_tex
        update_parameter_tex(metadatapath)
    elif args.create_pdf:
        metadatapath = args.create_pdf
        create_pdf(metadatapath)
    elif args.create_system_model_list_pdf:
        create_system_model_list_pdf()
    elif args.metadata or args.md:
        if args.md:
            args.metadata = "metadata.yml"
        data = core.get_metadata_from_file(args.metadata)

        print(f"\n  {bgreen('content of '+args.metadata)}\n")

        pprint.pprint(data, indent=1)
        print("")
        return
    elif args.key:
        print("Random entity-key: ", core.gen_random_entity_key())
        return
    elif args.bootstrap_db:
        bootstrap_db(db="main")
    elif args.bootstrap_test_db:
        bootstrap_db(db="test")
    elif args.show_entity_info:
        key = args.show_entity_info
        core.print_entity_info(key)
    elif args.test_logging:
        core.send_log_messages()
    elif args.version:
        print("Version", release.__version__)
    elif args.start_workers:
        start_workers()
    elif args.prepare_script:
        metadatapath = args.prepare_script
        prepare_script(metadatapath)
    elif args.run_interactive_environment:
        args = args.run_interactive_environment
        run_interactive_environment(args)
    else:
        print("This is the ackrep_core command line tool\n")
        argparser.print_help()


# worker functions


def create_new_entity():

    entity_class = dialoge_entity_type()
    dir_name = questionary.text("directory name?", default="unnamed_entity").ask()

    try:
        os.mkdir(dir_name)
    except FileExistsError:
        print(yellow(f"directory `{dir_name}` already exists!"))
        q = input("Write into it? (y|N)")
        if q != "y":
            print(bred("aborted."))

    field_values = dialoge_field_values(entity_class)

    path = os.path.join(dir_name, "metadata.yml")
    core.convert_dict_to_yaml(field_values, target_path=path)


def check_all_solutions():

    returncodes = []
    for ps in models.ProblemSolution.objects.all():
        # res = check(ps.key, exitflag=False)

        res = check_with_docker(ps.key, exitflag=False)
        returncodes.append(res.returncode)
        print("---")

    if returncodes == 0:
        print(bgreen("All checks successfull."))
    else:
        print(bred("Some check failed."))

    exit(sum(returncodes))


def check_all_system_models():

    returncodes = []
    for sm in models.SystemModel.objects.all():
        # res = check(sm.key, exitflag=False)
        if sm.key == "YHS5B":
            print("skipping mmc!")
            print("---")
            continue
        res = check_with_docker(sm.key, exitflag=False)
        returncodes.append(res.returncode)
        print("---")

    if returncodes == 0:
        print(bgreen("All checks successfull."))
    else:
        print(bred("Some check failed."))

    exit(sum(returncodes))

def test_ci():
    file_name = "ci_results.yaml"
    if os.path.exists(file_name):
        os.remove(file_name)
    returncodes = []
    for key in ["ZPPRG", "UXMFA", "IWTAE", "HOZEE"]:
        start_time = time.time()
        res = check_with_docker(key, exitflag=False)
        runtime = round(time.time() - start_time, 0)
        result = res.returncode
        if res.returncode == 0:
            issues = ""
        else:
            issues = res.stdout
        date = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        content = {key: {"result": result, "issues": issues, "runtime": runtime, "date": date}}
        with open(file_name, 'a') as file:
            documents = yaml.dump(content, file)
        
        returncodes.append(res.returncode)
        print("---")

    if returncodes == 0:
        print(bgreen("All checks successfull."))
    else:
        print(bred("Some check failed."))

    # exit(sum(returncodes))
    exit(0)

def check(arg0: str, exitflag: bool = True):
    """

    :param arg0:        either an entity key or the path to the respective metadata.yml
    :param exitflag:    determine whether the program should exit at the end of this function

    :return:            container of subprocess.run (if exitflag == False)
    """

    entity, key = get_entity_and_key(arg0)

    assert isinstance(entity, models.ProblemSolution) or isinstance(entity, models.SystemModel)

    print(f'Checking {bright(str(entity))} "({entity.name}, {entity.estimated_runtime})"')
    res = core.check_generic(key=key)

    if res.returncode == 0:
        print(bgreen("Success."))
    elif res.returncode == 2:
        print(yellow("Inaccurate."))
    else:
        print(bred("Fail."))

    if exitflag:
        exit(res.returncode)
    else:
        return res


def check_with_docker(arg0: str, exitflag: bool = True):
    """run the correct environment specification

    :param arg0:        either an entity key or the path to the respective metadata.yml
    :param exitflag:    determine whether the program should exit at the end of this function

    :return:            container of subprocess.run (if exitflag == False)
    """

    entity, key = get_entity_and_key(arg0)

    assert isinstance(entity, models.ProblemSolution) or isinstance(entity, models.SystemModel)

    print(f'Checking {bright(str(entity))} "({entity.name}, {entity.estimated_runtime})"')
    res = core.check(key=key)

    if res.returncode == 0:
        print(bgreen("Success."))
    elif res.returncode == 2:
        print(yellow("Inaccurate."))
    else:
        print(bred("Fail."))

    if exitflag:
        exit(res.returncode)
    else:
        return res


def get_metadata_path_from_key(arg0: str, absflag: bool = True, exitflag: bool = True):
    """

    :param arg0:        key
    :param absflag:     flag to determine if absolute (True) or relative path (False)
                        should be returned
    :param exitflag:    determine whether the program should exit at the end of this function

    :return:            container of subprocess.run (if exitflag == False)
    """

    entity = core.get_entity(arg0)

    path = os.path.join(entity.base_path, "metadata.yml")
    if absflag:
        path = os.path.join(core.root_path, path)
    print(path)

    if exitflag:
        exit(0)
    else:
        return path


def update_parameter_tex(arg0: str, exitflag: bool = True):
    """

    :param arg0:        either an entity key or the path to the respective metadata.yml
    :param exitflag:    determine whether the program should exit at the end of this function

    :return:            container of subprocess.run (if exitflag == False)
    """

    entity, key = get_entity_and_key(arg0)

    assert isinstance(entity, models.SystemModel)
    # IPS()
    res = system_model_management.update_parameter_tex(key=key)


def create_pdf(arg0: str, exitflag: bool = True):
    """

    :param arg0:        either an entity key or the path to the respective metadata.yml
    :param exitflag:    determine whether the program should exit at the end of this function

    :return:            container of subprocess.run (if exitflag == False)
    """

    entity, key = get_entity_and_key(arg0)

    assert isinstance(entity, models.SystemModel), f"{key} is not a system model key!"
    # IPS()
    res = system_model_management.create_pdf(key=key)
    if res.returncode == 0:
        print(bgreen("Success."))
    else:
        print(bred("Fail."))

    if exitflag:
        exit(res.returncode)
    else:
        return res


def create_system_model_list_pdf(exitflag: bool = True):
    res = system_model_management.create_system_model_list_pdf()
    if res.returncode == 0:
        print(f"PDF is stored in {core.root_path}/local_outputs/ .")
        print(bgreen("Success."))
    else:
        print(bred("Fail."))

    if exitflag:
        exit(res.returncode)
    else:
        return res


def dialoge_entity_type():
    entities = models.get_entities()

    # noinspection PyProtectedMember
    choices = [e._type for e in entities]

    type_map = dict(zip(choices, entities))

    res = questionary.select(
        "\nWhich entity do you want to create?\n(Use `..` to answer all remaining questions with default values).",
        choices=choices,
    ).ask()  # returns value of selection

    return type_map[res]


def dialoge_field_values(entity_class):

    fields = entity_class.get_fields()

    entity = entity_class(key=core.gen_random_entity_key())

    res_dict = dict()

    # prefill the dict with default values
    for f in fields:
        default = getattr(entity, f.name, None)
        if default is None:
            default = ""
        res_dict[f.name] = default

    # noinspection PyProtectedMember
    res_dict["type"] = entity._type

    # now ask the user on each value
    omit_flag = False
    for f in fields:
        question = f"{f.name} ? "
        default = res_dict[f.name]

        qres = questionary.text(question, default=default).skip_if(omit_flag, default=default).ask()

        # shortcut to omit further questions
        if qres == "..":
            omit_flag = True
            qres = default

        # pragmatic way to handle lists
        if f.name.endswith("_list"):
            qres = qres.split(";")

        res_dict[f.name] = qres

    return res_dict


def bootstrap_db(db: str) -> None:
    """
    This function basically executes
      `rm -f db.sqlite3; python manage.py migrate --run-syncdb`
    for either the main or the test database.

    :param db:      'main' or 'test'
    """

    valid_values = ("main", "test")
    assert db in valid_values

    old_workdir = os.getcwd()
    os.chdir(core.core_pkg_path)

    if db == "main":
        fname = "db.sqlite3"
    else:
        fname = "db_for_unittests.sqlite3"

    env_db_path = os.environ.get("ACKREP_DATABASE_PATH")
    db_path = os.path.abspath(fname)

    if env_db_path is not None and env_db_path != db_path:
        msg = (
            "Inconsistent values for bootstrapping database: "
            f"internal db_path: {db_path}, env var ACKREP_DATABASE_PATH: {env_db_path}"
        )
        raise ValueError(msg)

    try:
        os.unlink(fname)
    except FileNotFoundError:
        pass

    settings.DATABASES["default"]["NAME"] = db_path
    management.call_command("migrate", "--run-syncdb")

    # return to old working dir
    os.chdir(old_workdir)


def start_workers():
    try:
        res = subprocess.run(["celery", "-A", "ackrep_web", "worker", "--loglevel=INFO", "-c" "4"])
    except KeyboardInterrupt:
        exit(0)


def prepare_script(arg0):
    """prepare exexscript and place it in transfer folder

    Args:
        arg0 (str): entity key or metadata path
    """
    _, key = get_entity_and_key(arg0)

    entity, c = core.get_entity_context(key)
    scriptpath = "/ackrep_transfer"
    core.create_execscript_from_template(entity, c, scriptpath=scriptpath)

    print(bgreen("Success."))


def run_interactive_environment(args):
    """get imagename, create transfer direktory, change permissions, start container"""
    if platform.system() != "Linux":
        msg = f"No support for {platform.system()}"
        raise NotImplementedError(msg)

    entity, key = get_entity_and_key(args[0])
    msg = f"{key} is not an EnvironmentSpecification key."
    assert isinstance(entity, models.EnvironmentSpecification), msg
    image_name = "ghcr.io/ackrep-org/" + entity.name
    print("\nRunning Interactive Docker Container. To Exit, press Ctrl+D.\n")
    old_cwd = os.getcwd()
    os.chdir(core.root_path)
    transfer_folder_name = "ackrep_transfer"
    os.makedirs(transfer_folder_name, exist_ok=True)
    # TODO: dynamic gid
    try:
        os.chown("ackrep_transfer", -1, 999)
    except PermissionError:
        core.logger.warning("Unable to change permissions for transfer folder.")
    # if host is windows, path still needs to have unix seps for inside container
    vol_host_path = os.path.join(core.root_path, transfer_folder_name)
    vol_container_path = "/code/" + transfer_folder_name
    vol_mapping = f"{vol_host_path}:{vol_container_path}"

    cmd = ["docker", "run", "-ti", "--rm"]

    cmd.extend(core.get_docker_env_vars())

    cmd.extend(core.get_data_repo_host_address())

    cmd.extend(["-v", vol_mapping, image_name])

    if len(args) == 1:
        cmd.extend(["/bin/bash", "-c", "cd ../; mc"])
    else:
        c = " ".join(args[1:])
        cmd.extend(["/bin/bash", "-c", c])

    print(cmd)
    res = subprocess.run(cmd)

    return res.returncode


def get_entity_and_key(arg0):
    """return entity and key for a given key or metadata path

    Args:
        arg0 (str): entity key or metadata path

    Returns:
        GenericEntity, str: entity, key
    """
    if len(arg0) == 5:
        entity = core.get_entity(arg0)
        key = arg0
    else:
        metadatapath = arg0
        if not metadatapath.endswith("metadata.yml"):
            metadatapath = os.path.join(metadatapath, "metadata.yml")
        meta_data = core.get_metadata_from_file(metadatapath)
        key = meta_data["key"]
        entity = core.get_entity(key)
    return entity, key
