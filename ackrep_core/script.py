import argparse
from . import core, models
import pprint

from colorama import Style, Fore
import questionary

from ipydex import IPS


def main():
    argparser = argparse.ArgumentParser()
    argparser.add_argument("-m", "--metadata", help="process metadata in yaml syntax (.yml file). ")
    argparser.add_argument("--md", help="shortcut for `-m metadata.yml`", action="store_true")
    argparser.add_argument("--pk", help="print a random primary key and exit", action="store_true")
    argparser.add_argument("--qq", help="test interactive questionnaire", action="store_true")
    argparser.add_argument("--dd", help="debug", action="store_true")

    args = argparser.parse_args()

    if args.pk:
        print("Random primary key: ", core.gen_random_pk())
        return

    if args.dd:
        IPS()
        return
    if args.qq:
        # !! debug/testing
        res = questionary.select(
            "What do you want to do?",
            choices=[
                'Order a pizza',
                'Make a reservation',
                'Ask for opening hours'
            ]).ask()  # returns value of selection

        IPS()
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


# helper functions


def bright(txt):
    return f"{Style.BRIGHT}{txt}{Style.RESET_ALL}"


def bgreen(txt):
    return f"{Fore.GREEN}{Style.BRIGHT}{txt}{Style.RESET_ALL}"


def bred(txt):
    return f"{Fore.RED}{Style.BRIGHT}{txt}{Style.RESET_ALL}"


def yellow(txt):
    return f"{Fore.YELLOW}{txt}{Style.RESET_ALL}"
