import os
import argparse
from . import core, models
import pprint
import subprocess

from colorama import Style, Fore
import questionary

from ipydex import IPS, activate_ips_on_exception

activate_ips_on_exception()


def main():
    argparser = argparse.ArgumentParser()
    argparser.add_argument("-m", "--metadata", help="process metadata in yaml syntax (.yml file). ")
    argparser.add_argument("--md", help="shortcut for `-m metadata.yml`", action="store_true")
    argparser.add_argument("--pk", help="print a random primary key and exit", action="store_true")
    argparser.add_argument("--qq", help="test interactive questionnaire", action="store_true")
    argparser.add_argument("--dd", help="start interactive IPython shell for debugging", action="store_true")
    argparser.add_argument("-cs","--check-solution", metavar="metadatafile",
                           help="check solution (specified by metadata file)")
    argparser.add_argument("-n", "--new", help="interactively create new entity", action="store_true")

    args = argparser.parse_args()

    if args.new:
        create_new_entity()

    elif args.dd:
        IPS()
    elif args.qq:

        entity = dialoge_entity_type()
        field_values = dialoge_field_values(entity)
        core.convert_dict_to_yaml(field_values, target_path="./metadata.yml")
        return
    elif args.check_solution:
        metadatapath = args.check_solution
        check_solution(metadatapath)

    elif args.metadata or args.md:
        if args.md:
            args.metadata = "metadata.yml"
        data = core.get_metadata_from_file(args.metadata)

        print(f"\n  {bgreen('content of '+args.metadata)}\n")

        pprint.pprint(data, indent=1)
        print("")
        return
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


def check_solution(metadatapath):
    solution_meta_data = core.get_metadata_from_file(metadatapath)

    # get path for solution
    solution_file = solution_meta_data["solution_file"]

    if solution_file != "solution.py":
        msg = "Arbitrary filename will be supported in the future"
        raise NotImplementedError(msg)

    basepath = os.path.split(metadatapath)[0]

    c = core.Container()  # this will be our easily accessible context dict

    # TODO: handle the filename (see also template)
    c.solution_path = basepath

    # currently we expect exactly one solution
    assert len(solution_meta_data["solved_problem_list"]) == 1

    problem_spec_key = solution_meta_data["solved_problem_list"][0]

    hintpath = os.path.join(basepath, "../demo_problem_spec/metadata.yml")
    problem_spec = core.get_entity(key=problem_spec_key, hint=hintpath)

    if problem_spec.problem_file != "problem.py":
        msg = "Arbitrary filename will be supported in the future"
        raise NotImplementedError(msg)

    # TODO: handle the filename (see also template)
    c.problem_spec_path = problem_spec.base_path

    method_package_keys = solution_meta_data["method_package_list"]

    c.method_package_list = []
    for method_package_key in method_package_keys:
        #hintpath = os.path.join(basepath, "../../method_packages/PyTrajectory/metadata.yml")
        #method_package = core.get_entity(key=method_package_key, hint=hintpath)
        #build_path = os.path.join(method_package.base_path, "_build")
        build_path_hint = os.path.join(basepath, "../../method_packages/PyTrajectory/_build")
        c.method_package_list.append(build_path_hint)

    context = dict(c.item_list())

    print("  ... Creating exec-script ... ")

    scriptname = "./execscript.py"

    core.render_template("templates/execscript.py.template", context, target_path=scriptname)

    print("  ... running exec-script ... ")

    # TODO: plug in containerization here:
    # Note: this hangs on any interactive element inside the script (such as IPS)
    res = subprocess.run(["python", scriptname], capture_output=True)
    res.exited = res.returncode
    res.stdout = res.stdout.decode("utf8")
    res.stderr = res.stderr.decode("utf8")

    if res.returncode == 0:
        print(bgreen("Success."))
    else:
        print(bred("Fail."))





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

    entity = entity_class(key=core.gen_random_key())

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


# helper functions


def bright(txt):
    return f"{Style.BRIGHT}{txt}{Style.RESET_ALL}"


def bgreen(txt):
    return f"{Fore.GREEN}{Style.BRIGHT}{txt}{Style.RESET_ALL}"


def bred(txt):
    return f"{Fore.RED}{Style.BRIGHT}{txt}{Style.RESET_ALL}"


def yellow(txt):
    return f"{Fore.YELLOW}{txt}{Style.RESET_ALL}"
