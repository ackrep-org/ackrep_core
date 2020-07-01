import argparse
from . import core, models
import pprint

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
    argparser.add_argument("--dd", help="debug", action="store_true")

    args = argparser.parse_args()

    if args.pk:
        print("Random primary key: ", core.gen_random_key())
        return

    if args.dd:
        IPS()
        return
    if args.qq:

        entity = dialoge_entity_type()
        field_values = dialoge_field_values(entity)
        core.convert_dict_to_yaml(field_values, target_path="./metadata.yml")
        return

    if args.md:
        args.metadata="metadata.yml"

    if args.metadata:
        data = core.get_metadata_from_file(args.metadata)

        print(f"\n  {bgreen('content of '+args.metadata)}\n")

        pprint.pprint(data, indent=1)
        print("")
        return

    print("This is the ackrep_core command line tool\n")
    argparser.print_help()


# worker functions

def dialoge_entity_type():
    entities = models.get_entities()

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
