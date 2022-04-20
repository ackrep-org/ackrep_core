import argparse
import subprocess
import pprint
import questionary
from django.core import management
from django.conf import settings

from ipydex import IPS, activate_ips_on_exception

from ackrep_core import system_model_management

activate_ips_on_exception()

from . import core
from . import models
from .util import *


def main():
    argparser = argparse.ArgumentParser()
    argparser.add_argument("--key", help="print a random key and exit", action="store_true")
    argparser.add_argument(
        "-cs", "--check-solution", metavar="metadatafile", help="check solution (specified by metadata file)"
    )
    argparser.add_argument(
        "--check-all-solutions", help="check all solutions (may take some time)", action="store_true"
    )
    argparser.add_argument(
        "-csm", "--check-system-model", metavar="metadatafile", help="check system_model (specified by metadata file)"
    )
    argparser.add_argument(
        "--update-parameter-tex",
        metavar="metadatafile",
        help="update parameters in tex file (entity is specified by metadata file)",
    )
    argparser.add_argument(
        "--create-pdf",
        metavar="metadatafile",
        help="create pdf of system model from tex file (entity is specified by metadata file)",
    )
    argparser.add_argument(
        "--get-metadata-abs-path-from-key", metavar="key", help="return absolute path to metadata file for a given key"
    )
    argparser.add_argument(
        "--get-metadata-rel-path-from-key", metavar="key", help="return path to metadata file (relative to repo root) for a given key"
    )
    argparser.add_argument(
        "--bootstrap-db", help="delete database and recreate it (without data)", action="store_true"
    )
    argparser.add_argument(
        "--bootstrap-test-db", help="delete database for unittests and recreate it (without data)", action="store_true"
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

    args = argparser.parse_args()

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
    elif args.check_solution:
        metadatapath = args.check_solution
        check_solution(metadatapath)
    elif args.check_all_solutions:
        check_all_solutions()
    elif args.check_system_model:
        metadatapath = args.check_system_model
        exitflag = not args.show_debug
        check_system_model(metadatapath, exitflag=exitflag)
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
    else:
        print("This is the ackrep_core command line tool\n")
        argparser.print_help()

    # TODO: add this to epilog or docs: useful comment: rm -f db.sqlite3; python manage.py migrate --run-syncdb


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
        res = check_solution(ps.key, exitflag=False)
        returncodes.append(res.returncode)
        print("---")

    return sum(returncodes)


# def check_solution(metadatapath=None, key=None, exitflag=True):
def check_solution(arg0: str, exitflag: bool = True):
    """

    :param arg0:        either an entity key or the path to the respective metadata.yml
    :param exitflag:    determine whether the program should exit at the end of this function

    :return:            container of subprocess.run (if exitflag == False)
    """

    try:
        entity = core.get_entities_with_key(arg0)[0]
        key = arg0
    except IndexError:
        metadatapath = arg0
        if not metadatapath.endswith("metadata.yml"):
            metadatapath = os.path.join(metadatapath, "metadata.yml")
        solution_meta_data = core.get_metadata_from_file(metadatapath)
        key = solution_meta_data["key"]
        entity = core.get_entity(key)

    assert isinstance(entity, models.ProblemSolution)

    print(f'Checking {bright(str(entity))} "({entity.name}, {entity.estimated_runtime})"')
    res = core.check_solution(key=key)

    if res.returncode == 0:
        print(bgreen("Success."))
    else:
        print(bred("Fail."))

    if exitflag:
        exit(res.returncode)
    else:
        return res


def check_system_model(arg0: str, exitflag: bool = True):
    """

    :param arg0:        either an entity key or the path to the respective metadata.yml
    :param exitflag:    determine whether the program should exit at the end of this function

    :return:            container of subprocess.run (if exitflag == False)
    """

    try:
        entity = core.get_entities_with_key(arg0)[0]
        key = arg0
    except IndexError:
        metadatapath = arg0
        if not metadatapath.endswith("metadata.yml"):
            metadatapath = os.path.join(metadatapath, "metadata.yml")
        system_model_meta_data = core.get_metadata_from_file(metadatapath)
        key = system_model_meta_data["key"]
        entity = core.get_entity(key)

    assert isinstance(entity, models.SystemModel)
    # IPS()
    print(f'Checking {bright(str(entity))} "({entity.name}, {entity.estimated_runtime})"')
    res = core.check_system_model(key=key)
    if res.returncode == 0:
        print(bgreen("Success."))
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

    entity = core.get_entities_with_key(arg0, raise_error_on_empty=True)[0]    

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

    try:
        entity = core.get_entities_with_key(arg0)[0]
        key = arg0
    except IndexError:
        metadatapath = arg0
        if not metadatapath.endswith("metadata.yml"):
            metadatapath = os.path.join(metadatapath, "metadata.yml")
        system_model_meta_data = core.get_metadata_from_file(metadatapath)
        key = system_model_meta_data["key"]
        entity = core.get_entity(key)

    assert isinstance(entity, models.SystemModel)
    # IPS()
    res = system_model_management.update_parameter_tex(key=key)


def create_pdf(arg0: str, exitflag: bool = True):
    """

    :param arg0:        either an entity key or the path to the respective metadata.yml
    :param exitflag:    determine whether the program should exit at the end of this function

    :return:            container of subprocess.run (if exitflag == False)
    """

    try:
        entity = core.get_entities_with_key(arg0)[0]
        key = arg0
    except IndexError:
        metadatapath = arg0
        if not metadatapath.endswith("metadata.yml"):
            metadatapath = os.path.join(metadatapath, "metadata.yml")
        system_model_meta_data = core.get_metadata_from_file(metadatapath)
        key = system_model_meta_data["key"]
        entity = core.get_entity(key)

    assert isinstance(entity, models.SystemModel)
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
        fname = "db_for_unittest.sqlite3"

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
