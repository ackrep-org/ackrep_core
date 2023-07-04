import argparse
import subprocess
import pprint
import time
import datetime
import signal
import os
import git
import yaml

from ipydex import IPS, activate_ips_on_exception

# import fast modules from ackrep
from ackrep_core import release
from ackrep_core import config_handler
from ackrep_core.util import bred, yellow, bgreen, timeout_handler, run_command, bright

# wrap access to modules which are slow to import
from ackrep_core import modules as acm

# if os.environ.get("CI") != "true":
if os.environ.get("ACKREP_DEVMODE") == "true":
    activate_ips_on_exception()

# timeout setup for entity check timeout, see https://stackoverflow.com/a/494273
if os.name != "nt":
    signal.signal(signal.SIGALRM, timeout_handler)


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
        "--check-all-entities",
        help="check all entities (solutions and models) (may take some time)",
        action="store_true",
    )
    argparser.add_argument("-da", "--download-artifacts", help="download artifacts from CI", action="store_true")
    argparser.add_argument(
        "--update-parameter-tex",
        metavar="metadatafile",
        help=(
            "update parameters of system model in tex file (system model entity is specified by metadata file or key)"
        ),
    )
    argparser.add_argument(
        "--create-pdf",
        metavar="metadatafile",
        help="create pdf of system model from tex file (system model entity is specified by metadata file or key)",
    )
    argparser.add_argument(
        "-uap",
        "--update-all-pdfs",
        help="update all pdfs of all system models from tex files",
        action="store_true",
    )
    argparser.add_argument(
        "--create-system-model-list-pdf",
        help="create pdf of all known system models, stored in <project_dir>/local_outputs/",
        action="store_true",
    )
    argparser.add_argument(
        "--get-metadata-abs-path-from-key",
        metavar="key",
        help="return absolute path to metadata file for a given key",
    )
    argparser.add_argument(
        "--get-metadata-rel-path-from-key",
        metavar="key",
        help="return path to metadata file (relative to repo root) for a given key",
    )
    argparser.add_argument("--bootstrap-db", help="delete database and recreate it (without data)", action="store_true")
    argparser.add_argument(
        "--bootstrap-test-db",
        help="delete database for unittests and recreate it (without data)",
        action="store_true",
    )

    argparser.add_argument(
        "--bootstrap-config",
        help=(
            "initialize the configuration file of the application. This assumes correct current working directory."
            "See docs (or source code) for more information. If config file already exists, just print its path."
        ),
        action="store_true",
    )

    argparser.add_argument(
        "--prepare-script",
        help=(
            "render the execscript and place it in the docker ackrep_data folder "
            "(specified by path to metadata file or key)"
        ),
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
    argparser.add_argument(
        "--jupyter",
        help="start jupyter server in environment with given key",
        metavar="key",
    )
    argparser.add_argument(
        "-p",
        "--pull-and-show-envs",
        help="pull env images and print infos (mainly used in CI run)",
        action="store_true",
    )
    argparser.add_argument(
        "-ufb",
        "--update-fallback-binaries",
        help="update files in fallback repo",
        action="store_true",
    )
    argparser.add_argument(
        "-ccm",
        "--create-compleib-models",
        help="automatically create models of compleib from template ",
        action="store_true",
    )
    argparser.add_argument(
        "--only",
        metavar="handle",
    )
    argparser.add_argument(
        "-tcm",
        "--test-compleib-models",
        help="test all compleib models",
        action="store_true",
    )
    argparser.add_argument(
        "-ccut",
        "--checkout-corresponding-ocse-ut-repo",
        help="try to find the ocse for ut repo locally and checkout the ut branch corresponding to current branch",
        action="store_true",
    )
    argparser.add_argument(
        "-upmd",
        "--update-metadata-from-property-report",
        help="load the results of a property report and write it to the corresponding model metadata",
        metavar="yamlpath",
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
        "--show-debug",
        help="set exitflags false in order to see underlying debug outputs",
        action="store_true",
    )

    argparser.add_argument("--show-entity-info", metavar="key", help="print out some info about the entity")

    argparser.add_argument(
        "--log",
        metavar="loglevel",
        help="specify log level: DEBUG (10), INFO, WARNING, ERROR, CRITICAL (50)",
        type=int,
    )

    argparser.add_argument(
        "--start-key",
        metavar="key",
        help="specify a key",
    )

    argparser.add_argument(
        "--test-logging",
        help="print out some dummy messages for each logging category",
        action="store_true",
    )
    argparser.add_argument(
        "--unittest",
        "-ut",
        help="some commands use this flag to behave differently during unittests",
        action="store_true",
    )
    argparser.add_argument(
        "--fast",
        help="some commands use this flag to behave speed up CI job",
        action="store_true",
    )
    argparser.add_argument(
        "-f",
        "--force",
        help="some commands use this flag",
        action="store_true",
    )

    args = argparser.parse_args()

    # non-exclusive options
    if args.log:
        acm.logging.logger.setLevel(int(args.log))

    if os.environ.get("ACKREP_PRINT_DEBUG_REPORT"):
        acm.logging.send_debug_report(print)
    else:
        # default: use logger.debug
        acm.logging.send_debug_report(acm.logging.logger.debug)

    # exclusive options
    if args.new:
        create_new_entity()
    elif args.dd:
        IPS()
    elif args.load_repo_to_db:
        startdir = args.load_repo_to_db
        acm.core.load_repo_to_db(startdir)
        print(bgreen("Done"))
    elif args.extend:
        startdir = args.extend
        acm.core.extend_db(startdir)
        print(bgreen("Done"))
    elif args.qq:

        entity = dialoge_entity_type()
        field_values = dialoge_field_values(entity)
        acm.core.convert_dict_to_yaml(field_values, target_path="./metadata.yml")
        return
    elif args.check:
        metadatapath = args.check
        check(metadatapath)
    elif args.check_with_docker:
        metadatapath = args.check_with_docker
        check_with_docker(metadatapath)
    elif args.check_all_entities:
        check_all_entities(args.unittest, args.fast)
    elif args.download_artifacts:
        download_artifacts()
    elif args.pull_and_show_envs:
        pull_and_show_envs()
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
    elif args.update_all_pdfs:
        update_all_pdfs(args.start_key)
    elif args.create_system_model_list_pdf:
        create_system_model_list_pdf()
    elif args.metadata or args.md:
        if args.md:
            args.metadata = "metadata.yml"
        data = acm.core.get_metadata_from_file(args.metadata)

        print(f"\n  {bgreen('content of '+args.metadata)}\n")

        pprint.pprint(data, indent=1)
        print("")
        return
    elif args.key:
        print("Random entity-key: ", acm.core.gen_random_entity_key())
        return
    elif args.bootstrap_config:
        config_handler.bootstrap_config_from_current_directory(force_new_config=args.force)
    elif args.bootstrap_db:
        bootstrap_db(db="main")
    elif args.bootstrap_test_db:
        bootstrap_db(db="test")
    elif args.show_entity_info:
        key = args.show_entity_info
        acm.core.print_entity_info(key)
    elif args.test_logging:
        acm.core.send_log_messages()
    elif args.version:
        print("Version", release.__version__)
    elif args.prepare_script:
        metadatapath = args.prepare_script
        prepare_script(metadatapath)
    elif args.run_interactive_environment:
        args = args.run_interactive_environment
        run_interactive_environment(args)
    elif args.jupyter:
        key = args.jupyter
        run_jupyter(key)
    elif args.update_fallback_binaries:
        update_fallback_binaries()
    elif args.create_compleib_models:
        create_compleib_models(args.only)
    elif args.test_compleib_models:
        test_compleib_models()
    elif args.checkout_corresponding_ocse_ut_repo:
        checkout_ut_repo()
    elif args.update_metadata_from_property_report:
        update_metadata_from_property_report(args.update_metadata_from_property_report)
    else:
        print("This is the ackrep_core command line tool\n")
        argparser.print_help()


# worker functions


def create_new_entity():
    import questionary

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
    acm.core.convert_dict_to_yaml(field_values, target_path=path)


def check_all_entities(unittest=False, fast=False):
    """this function is called during CI.
    All (checkable) entities are checked and the results stored in a yaml file."""

    import yaml
    from git import Repo

    # setup ci_results folder
    date = datetime.datetime.now()
    date_string = date.strftime("%Y_%m_%d__%H_%M_%S")
    file_name = "ci_results__" + date_string + ".yaml"
    file_path = os.path.join(acm.core.CONF.ACKREP_ROOT_PATH, "artifacts", "ci_results", file_name)
    os.makedirs(os.path.join(acm.core.CONF.ACKREP_ROOT_PATH, "artifacts", "ci_results"), exist_ok=True)

    content = {"commit_logs": {}}
    # save the commits of the current ci job
    current_data_repo = os.path.split(acm.core.CONF.ACKREP_DATA_PATH)[-1]
    for repo_name in [current_data_repo, "ackrep_core"]:
        repo = Repo(f"{acm.core.CONF.ACKREP_ROOT_PATH}/{repo_name}")
        commit = repo.commit("HEAD")
        commit_date = time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime(commit.committed_date))
        log_dict = {
            "date": commit_date,
            "branch": repo.active_branch.name,
            "sha": commit.hexsha,
            "message": commit.summary,
            "author": commit.author.name,
        }
        content["commit_logs"][repo_name] = log_dict

    content["ci_logs"] = {}
    # log some info about the ci run (url)
    if os.environ.get("CIRCLECI"):
        content["ci_logs"]["build_url"] = os.environ.get("CIRCLE_BUILD_URL")
        content["ci_logs"]["build_number"] = os.environ.get("CIRCLE_BUILD_NUM")

    with open(file_path, "a") as file:
        yaml.dump(content, file)

    returncodes = []
    failed_entities = []
    if unittest:
        entity_list = [acm.core.get_entity("UXMFA"), acm.core.get_entity("LRHZX"), acm.core.get_entity("7WIQH")]
    else:
        entity_list = (
            list(acm.models.Notebook.objects.all())
            + list(acm.models.ProblemSolution.objects.all())
            + list(acm.models.SystemModel.objects.all())
        )
        # for faster CI testing:
        if fast:
            acm.logging.logger.warning(
                "--- Using the fast version of check all entities, not all entities will be checked! --- "
            )
            entity_list = [
                acm.core.get_entity("UXMFA"),  # sm lorenz
                acm.core.get_entity("7WIQH"),  # nb limit cycle van der pol
                acm.core.get_entity("CZKWU"),  # ps nonlinear_trajectory_electrical_resistance
                acm.core.get_entity("IG3GA"),  # sm linear transport (pde -> qt)
            ]
    for entity in entity_list:
        key = entity.key

        start_time = time.time()
        res = check_with_docker(key, exitflag=False)
        runtime = round(time.time() - start_time, 1)

        result = res.returncode
        # collect the created data files (plots, htmls, ...) and place them in the artifact folder for later download
        if res.returncode == 0:
            issues = ""

            # copy plot or notebook to collection directory
            dest_dir_plots = os.path.join(acm.core.CONF.ACKREP_ROOT_PATH, "artifacts", "ackrep_plots")
            dest_dir_notebooks = os.path.join(acm.core.CONF.ACKREP_ROOT_PATH, "artifacts", "ackrep_notebooks")

            if isinstance(entity, acm.models.ProblemSolution) or isinstance(entity, acm.models.SystemModel):
                # copy entire folder since there could be multiple images with arbitrary names
                src = f"dummy:/code/{entity.base_path}/_data/."
                dest_folder = os.path.join(dest_dir_plots, key)
                dest = dest_folder
            elif isinstance(entity, acm.models.Notebook):
                html_file_name = entity.notebook_file.replace(".ipynb", ".html")
                src = f"dummy:/code/{entity.base_path}/{html_file_name}"
                dest_folder = os.path.join(dest_dir_notebooks, key)
                dest = os.path.join(dest_folder, html_file_name)
            else:
                raise TypeError(f"{key} is not of a checkable type")

            os.makedirs(dest_folder, exist_ok=True)
            # docker cp has to be used, see https://circleci.com/docs/2.0/building-docker-images#mounting-folders
            run_command(["docker", "cp", src, dest], logger=acm.logging.logger)

            # remove tex and pdf files to prevent them being copied
            for file in os.listdir(dest_folder):
                if not (".png" in file or ".html" in file):
                    os.remove(os.path.join(dest_folder, file))

        else:
            issues = res.stdout
        date_string = date.strftime("%Y-%m-%d %H:%M:%S")

        content = {key: {"result": result, "issues": issues, "runtime": runtime, "date": date_string}}

        if "Calculated with " in res.stdout:
            version = res.stdout.split("Calculated with ")[-1].split("\n\n")[0]
            content[key]["env_version"] = version

        with open(file_path, "a") as file:
            yaml.dump(content, file)

        returncodes.append(res.returncode)
        if res.returncode != 0:
            failed_entities.append(key)
        print("---")

    if sum(returncodes) == 0:
        print(bgreen(f"All {len(entity_list)} checks successfull."))
    else:
        print(bred(f"{len(failed_entities)}/{len(entity_list)} checks failed."))
        print("Failed entities:", failed_entities)

    exit(sum(returncodes))


def check(arg0: str, exitflag: bool = True):
    """

    :param arg0:        either an entity key or the path to the respective metadata.yml
    :param exitflag:    determine whether the program should exit at the end of this function

    :return:            container of subprocess.run (if exitflag == False)
    """

    entity, key = get_entity_and_key(arg0)

    assert isinstance(
        entity, (acm.models.ProblemSolution, acm.models.SystemModel, acm.models.Notebook)
    ), f"No support for entity with type {type(entity)}."

    print(f'Checking {bright(str(entity))} "({entity.name}, {entity.estimated_runtime})"')

    # set timeout
    if not os.name == "nt":
        signal.alarm(acm.settings.ENTITY_TIMEOUT)
    try:
        if isinstance(entity, (acm.models.ProblemSolution, acm.models.SystemModel)):
            # TODO: this cmd seems to be obsolete
            cmd = [f"core.check_generic(key={key}"]
            res = acm.core.check_generic(key=key)
        elif isinstance(entity, acm.models.Notebook):
            path = os.path.join(acm.core.CONF.ACKREP_ROOT_PATH, entity.base_path, entity.notebook_file)
            cmd = ["jupyter", "nbconvert", "--execute", "--to", "html", path]
            res = run_command(cmd, logger=acm.logging.logger, capture_output=False)
        else:
            raise NotImplementedError
    except TimeoutError as exc:
        msg = f"Entity calculation reached timeout ({acm.settings.ENTITY_TIMEOUT}s)."
        acm.logging.logger.error(msg)
        res = subprocess.CompletedProcess(cmd, returncode=1, stdout="", stderr=f"Entity check timed out.\n{exc}")

    # cancel timeout
    if not os.name == "nt":
        signal.alarm(0)

    env_version = get_environment_version(entity)
    if env_version != "Unknown":
        print(f"\nCalculated with {env_version}\n")

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


def get_environment_version(entity: "acm.models.GenericEntity"):
    try:
        env_key = entity.compatible_environment
        if env_key == "" or env_key is None:
            env_key = acm.settings.DEFAULT_ENVIRONMENT_KEY
        env_name = acm.core.get_entity(env_key).name
        dockerfile_name = "Dockerfile_" + env_name
        path = os.path.join(acm.core.CONF.ACKREP_ROOT_PATH, dockerfile_name)
        with open(path, "r") as docker_file:
            lines = docker_file.readlines()
        if "LABEL" in lines[-1]:
            version = lines[-1].split('org.opencontainers.image.description "')[-1].split(". |")[0]
        else:
            version = "Unknown"
    except:
        version = "Unknown"

    return version


def check_with_docker(arg0: str, exitflag: bool = True):
    """run the correct environment specification

    :param arg0:        either an entity key or the path to the respective metadata.yml
    :param exitflag:    determine whether the program should exit at the end of this function

    :return:            container of subprocess.run (if exitflag == False)
    """

    entity, key = get_entity_and_key(arg0)

    assert isinstance(
        entity, (acm.models.ProblemSolution, acm.models.SystemModel, acm.models.Notebook)
    ), f"No support for entity with type {type(entity)}."

    print(f'Checking {bright(str(entity))} "({entity.name}, {entity.estimated_runtime})"')
    res = acm.core.check(key=key)

    if res.returncode == 0:
        print(res.stdout)
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

    entity = acm.core.get_entity(arg0)

    path = os.path.join(entity.base_path, "metadata.yml")
    if absflag:
        path = os.path.join(acm.core.CONF.ACKREP_ROOT_PATH, path)
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

    assert isinstance(entity, acm.models.SystemModel)
    # IPS()
    res = acm.system_model_management.update_parameter_tex(key=key)


def create_pdf(arg0: str, exitflag: bool = True):
    """

    :param arg0:        either an entity key or the path to the respective metadata.yml
    :param exitflag:    determine whether the program should exit at the end of this function

    :return:            container of subprocess.run (if exitflag == False)
    """

    entity, key = get_entity_and_key(arg0)

    assert isinstance(entity, acm.models.SystemModel), f"{key} is not a system model key!"
    # IPS()
    res = acm.system_model_management.create_pdf(key=key)
    if res.returncode == 0:
        print(bgreen("Success."))
    else:
        print(bred("Fail."))

    if exitflag:
        exit(res.returncode)
    else:
        return res


def update_all_pdfs(start_key=None):
    """

    :param arg0:        either an entity key or the path to the respective metadata.yml
    :param exitflag:    determine whether the program should exit at the end of this function

    :return:            container of subprocess.run (if exitflag == False)
    """
    failed_entities = []
    entity_list = list(acm.models.SystemModel.objects.all())

    skip_until_key = True

    for i, e in enumerate(entity_list):
        if start_key is not None and skip_until_key:
            if start_key == e.key:
                skip_until_key = False
            else:
                acm.core.logger.info(f"skipping {e}")
                continue
        else:
            skip_until_key = False

        print(bright(e))
        model_too_big = False
        d = yaml.load(e.erk_data, yaml.FullLoader)
        try:
            rep = d['R2928["has model representation"]']
            dim = d['R2928["has model representation"]'][list(rep.keys())[0]]['R2112["has state dimension"]']
            model_too_big = dim > 20
        except KeyError:
            pass

        try:
            acm.system_model_management.update_parameter_tex(e.key, omit_parameters=model_too_big)
        except Exception as exc:
            acm.logging.logger.warn(f"Parameter update Error, {exc}, maybe entity doesnt have params?")

        res = acm.system_model_management.create_pdf(key=e.key, skip_check=model_too_big)
        if res.returncode == 0:
            print(bgreen("Success."))
        else:
            print(bred("Fail."))
            failed_entities.append(e.key)

    if len(failed_entities) == 0:
        print(bgreen(f"All {len(entity_list)} builds successfull."))
    else:
        print(bred(f"{len(failed_entities)}/{len(entity_list)} builds failed."))
        print("Failed entities:", failed_entities)

    exit(len(failed_entities))


def create_system_model_list_pdf(exitflag: bool = True):
    res = acm.system_model_management.create_system_model_list_pdf()
    if res.returncode == 0:
        print(f"PDF is stored in {acm.core.CONF.ACKREP_ROOT_PATH}/local_outputs/ .")
        print(bgreen("Success."))
    else:
        print(bred("Fail."))

    if exitflag:
        exit(res.returncode)
    else:
        return res


def dialoge_entity_type():
    import questionary

    entities = acm.models.get_entities()

    # noinspection PyProtectedMember
    choices = [e._type for e in entities]

    type_map = dict(zip(choices, entities))

    res = questionary.select(
        "\nWhich entity do you want to create?\n(Use `..` to answer all remaining questions with default values).",
        choices=choices,
    ).ask()  # returns value of selection

    return type_map[res]


def dialoge_field_values(entity_class):
    import questionary

    fields = entity_class.get_fields()

    entity = entity_class(key=acm.core.gen_random_entity_key())

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

    from django.core import management

    valid_values = ("main", "test")
    assert db in valid_values

    old_workdir = os.getcwd()
    os.chdir(acm.core.core_pkg_path)

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

    acm.settings.DATABASES["default"]["NAME"] = db_path
    management.call_command("migrate", "--run-syncdb")

    # return to old working dir
    os.chdir(old_workdir)


def prepare_script(arg0):
    """prepare exexscript and place it in ackrep_data folder

    Args:
        arg0 (str): entity key or metadata path
    """
    _, key = get_entity_and_key(arg0)

    entity, c = acm.core.get_entity_context(key)
    scriptpath = os.path.join(acm.core.CONF.ACKREP_ROOT_PATH, "ackrep_data")
    acm.core.create_execscript_from_template(entity, c, scriptpath=scriptpath)

    print(bgreen("Success."))


def run_interactive_environment(args):
    """get imagename, start container"""

    import platform

    if platform.system() != "Linux":
        msg = f"No support for {platform.system()}"
        raise NotImplementedError(msg)

    entity, key = get_entity_and_key(args[0])
    msg = f"{key} is not an EnvironmentSpecification key."
    assert isinstance(entity, acm.models.EnvironmentSpecification), msg
    print("\nRunning Interactive Docker Container. To Exit, press Ctrl+D.\n")

    container_id = acm.core.start_idle_container(entity.name, try_to_use_local_image=False)

    acm.logging.logger.info(f"Ackrep command running in Container: {container_id}")
    host_uid = acm.core.get_host_uid()

    if len(args) == 1:
        cmd = ["docker", "exec", "-ti", "--user", host_uid, container_id]
        cmd.extend(["/bin/bash"])
    else:
        cmd = ["docker", "exec", "-t", "--user", host_uid, container_id]
        c = " ".join(args[1:])
        cmd.extend(["/bin/bash", "-c", c])

    print(cmd)
    res = run_command(cmd, capture_output=False)

    print("Shutting down container...")
    run_command(["docker", "stop", container_id], logger=acm.logging.logger, capture_output=True)

    return res.returncode


def run_jupyter(key):
    """run jupyter server out of docker environment container
    jupyter notebook --notebook-dir=/code/ackrep_data --ip='*' --port=8888 --no-browser --allow-root
    """

    entity, key = get_entity_and_key(key)
    msg = f"{key} is not an EnvironmentSpecification key."
    assert isinstance(entity, acm.models.EnvironmentSpecification), msg

    # run_command([f"docker stop $(docker ps --filter name={entity.name} -q)"], shell=True)
    find_cmd = ["docker", "ps", "--filter", f"name={entity.name}", "-q"]
    res = run_command(find_cmd, capture_output=True)
    if len(res.stdout) > 0:
        ids = res.stdout.split("\n")[:-1]
        for i in ids:
            stop_cmd = ["docker", "stop", i]
            run_command(stop_cmd, capture_output=True)

    print("\nRunning Jupyter Server in Docker Container. To Stop the Server, press Ctrl+C twice.")
    print("To access the Notebook, click one of the provided links below.\n")

    port_dict = {8888: 8888}
    container_id = acm.core.start_idle_container(entity.name, try_to_use_local_image=True, port_dict=port_dict)

    acm.logging.logger.info(f"Ackrep command running in Container: {container_id}")
    host_uid = acm.core.get_host_uid()
    cmd = ["docker", "exec", "-ti", "--user", host_uid, container_id]

    cmd.extend(
        [
            "jupyter",
            "notebook",
            "--notebook-dir=/code/ackrep_data",
            "--ip='*'",
            "--port=8888",
            "--no-browser",
            "--allow-root",
        ]
    )

    print(cmd)
    res = run_command(cmd, capture_output=False)

    print("Shutting down container...")
    run_command(["docker", "stop", container_id], logger=acm.logging.logger, capture_output=True)

    return res.returncode


def download_artifacts():
    acm.core.download_and_store_artifacts(acm.settings.ACKREP_DATA_BRANCH)
    print(bgreen("Done."))


def pull_and_show_envs():
    """this function pulls the most recent environment version and prints out information about this version
    it is primarily used inside the docker container to ensure image validity"""
    entities = list(acm.models.EnvironmentSpecification.objects.all())
    print("\nEnvironment Infos:\n")
    for entity in entities:
        env_key = entity.key
        env_name = entity.name

        dockerfile_name = "Dockerfile_" + env_name
        # pull most recent image
        cmd = ["docker", "pull", f"ghcr.io/ackrep-org/{env_name}:latest"]
        pull = run_command(cmd, acm.logging.logger, capture_output=True)
        # get version info of image
        if os.environ.get("CI") == "true":
            dockerfile_path = f"../{dockerfile_name}"
        else:
            dockerfile_path = os.path.join(
                acm.core.CONF.ACKREP_ROOT_PATH, "ackrep_deployment/dockerfiles/ackrep_core", dockerfile_name
            )
        cmd = [
            "docker",
            "run",
            "--entrypoint",
            "tail",
            f"ghcr.io/ackrep-org/{env_name}:latest",
            "-1",
            dockerfile_path,
        ]
        res = run_command(cmd, acm.logging.logger, capture_output=True)
        infos = res.stdout.split('org.opencontainers.image.description "')[-1].split("|")

        print(f"{env_name} ({env_key}):")
        row_template = "  {}"
        for info in infos:
            print(row_template.format(info))
        print()
    default_key = acm.settings.DEFAULT_ENVIRONMENT_KEY
    default_name = acm.core.get_entity(default_key).name
    print(f"Default environment is {default_name} ({default_key})\n")


def get_entity_and_key(arg0):
    """return entity and key for a given key or metadata path

    Args:
        arg0 (str): entity key or metadata path

    Returns:
        GenericEntity, str: entity, key
    """
    if len(arg0) == 5:
        entity = acm.core.get_entity(arg0)
        key = arg0
    else:
        metadatapath = arg0
        if not metadatapath.endswith("metadata.yml"):
            metadatapath = os.path.join(metadatapath, "metadata.yml")
        meta_data = acm.core.get_metadata_from_file(metadatapath)
        key = meta_data["key"]
        entity = acm.core.get_entity(key)
    return entity, key


def update_fallback_binaries():
    import shutil

    fallback_bin_location = os.path.join(acm.core.CONF.ACKREP_ROOT_PATH, "ackrep_fallback_binaries")

    entity_list = list(acm.models.ProblemSolution.objects.all()) + list(acm.models.SystemModel.objects.all())

    for entity in entity_list:
        key = entity.key
        base_path = entity.base_path
        plot_dir = os.path.join(acm.core.CONF.ACKREP_ROOT_PATH, base_path, "_data", "plot.png")
        if os.path.isfile(plot_dir):
            os.makedirs(os.path.join(fallback_bin_location, key), exist_ok=True)
            target_dir = os.path.join(fallback_bin_location, key, "plot.png")
            shutil.copy(plot_dir, target_dir)
        else:
            acm.logging.logger.info(f"{entity} plot was not found.")


def create_compleib_models(arg0):
    acm.automatic_model_creation.create_compleib_models_from_template(arg0)


def test_compleib_models():
    entity_list = list(acm.models.SystemModel.objects.all())
    com_models = [i for i in entity_list if "CO" in i.key]
    for e in com_models:
        print(bright(e))
        res = acm.core.check_generic(e.key)
        if res.returncode == 0:
            print(bgreen("Success."))
        elif res.returncode == 2:
            print(yellow("Inaccurate."))
        else:
            print(bred("Fail."))


def checkout_ut_repo():
    core_repo = git.Repo(acm.core.core_pkg_path)
    core_branch = core_repo.active_branch.name

    # 1. find erk_data ut directory
    path = os.path.split(acm.core.CONF.ERK_DATA_OCSE_UT_CONF_PATH)[0]
    acm.core.logger.info(f"ocse ut repo path: {path}")
    erk_data_repo = git.Repo(path)

    # 2. checkout corresponding branch
    erk_data_branch = erk_data_repo.active_branch.name
    erk_data_branches = erk_data_repo.git.branch("-r")  # check remote branches

    target_name = f"ut__ackrep__{core_branch}"
    default_name = f"ut__ackrep__main"

    ## corresponding branch exists
    if target_name in erk_data_branches:
        erk_data_repo.git.checkout(target_name)
        erk_data_repo.git.pull()
        acm.core.logger.info("UT branch checked out successfully.")
    ## corresponsing branch does not exist, use default main branch
    elif default_name in erk_data_branches:
        erk_data_repo.git.checkout(default_name)
        erk_data_repo.git.pull()
        acm.core.logger.warning(f"Falling back to {default_name}.")
    ## no ut branch found --> error
    else:
        acm.core.logger.error(
            acm.util.bred(
                f"No corresponding erk_data ut branch ({target_name, default_name}) found in {erk_data_branches}!"
            )
        )
        raise ValueError(f"No unittest branch with the right name was found.")


def update_metadata_from_property_report(property_path):
    import yaml
    import pyerk as p
    from django.db.models import Q
    from ackrep_core.models import PyerkEntity
    from ackrep_web.util import reload_data_if_necessary

    p.erkloader.load_mod_from_path(modpath=acm.core.settings.CONF.ERK_DATA_OCSE_MAIN_PATH, prefix="ct")
    reload_data_if_necessary()

    # load property yaml
    with open(property_path, "r") as f:
        property_dict = yaml.load(f, Loader=yaml.FullLoader)

    # iterate property dict
    # key = entity key, value = dict(properties)
    for key, value in property_dict.items():
        # load metadata of system model
        entity, key = get_entity_and_key(key)
        metadata_path = os.path.join(acm.core.CONF.ACKREP_ROOT_PATH, entity.base_path, "metadata.yml")
        with open(metadata_path, "r") as f:
            meta_dict = yaml.load(f, Loader=yaml.FullLoader)

        # iterate properties
        # key = erk key of property, value = property data
        for prop, data in value.items():

            # TODO move this to config?
            positive_relation = 'R8303["has general system property"]'
            negative_relation = 'R6458["does not have general system property"]'

            if data["result"] == False:
                # switch meaning positive and negative relations and recycle same code
                buf = positive_relation
                positive_relation = negative_relation
                negative_relation = buf

            if data["result"] is not None:

                # only filter uri
                property_list = list(PyerkEntity.objects.filter(Q(uri__icontains=prop)))
                if len(property_list) != 1:
                    acm.core.logger.warn(f"Entity not unique or none was found. {property_list}")
                property_key_label = (
                    property_list[0].__str__().split("#")[-1].replace("__", '["').replace("_", " ") + '"]'
                )

                # check if property is already set
                ## make sure meta data entry exists
                if not "erk_data" in meta_dict.keys():
                    acm.core.logger.warn(f"Model {entity} has no metadata yet! Adding some automatically.")
                    meta_dict["erk_data"] = {}

                # metadata has no properties: add current prop
                if not positive_relation in meta_dict["erk_data"].keys():
                    meta_dict["erk_data"][positive_relation] = [property_key_label]
                    # print("new property added")
                # metadata already has current prop: do nothing
                elif property_key_label in meta_dict["erk_data"][positive_relation]:
                    # print("prop already exists")
                    pass
                # just add property to existing ones
                else:
                    meta_dict["erk_data"][positive_relation].append(property_key_label)
                    # print("property added to others")

                # metadata has opposite relation
                if (
                    negative_relation in meta_dict["erk_data"].keys()
                    and property_key_label in meta_dict["erk_data"][negative_relation]
                ):
                    acm.core.logger.warn(f"Evaluation of property {prop} for {entity} changed to {data['result']}")
                    meta_dict["erk_data"][negative_relation].remove(property_key_label)
                # IPS()
        with open(metadata_path, "w") as f:
            yaml.dump(meta_dict, f, allow_unicode=True)

        # IPS()
        # TODO automate process of identifying relation. maybe it is a representation property
