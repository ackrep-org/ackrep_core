import os
import argparse

from ipydex import IPS, activate_ips_on_exception

activate_ips_on_exception()

from . import core, models
from .util import *
import pprint
import subprocess

import questionary


def main():
    argparser = argparse.ArgumentParser()
    argparser.add_argument("--key", help="print a random key and exit", action="store_true")
    argparser.add_argument(
        "-cs", "--check-solution", metavar="metadatafile", help="check solution (specified by metadata file)"
    )
    argparser.add_argument(
        "--check-all-solutions", help="check all solutions (may take some time)", action="store_true"
    )
    argparser.add_argument("-n", "--new", help="interactively create new entity", action="store_true")
    argparser.add_argument("-l", "--load-repo-to-db", help="load repo to database", metavar="path")
    argparser.add_argument("-e", "--extend", help="extend database with repo", metavar="path")
    argparser.add_argument("--qq", help="create new metada.yml based on interactive questionnaire", action="store_true")

    # for development only
    argparser.add_argument("--dd", help="start interactive IPython shell for debugging", action="store_true")
    argparser.add_argument("--md", help="shortcut for `-m metadata.yml`", action="store_true")
    argparser.add_argument("-m", "--metadata", help="process metadata in yaml syntax (.yml file). ")

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
