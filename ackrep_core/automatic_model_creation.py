import os
from ipydex import IPS
from . import core
import re
import jinja2
import matlab.engine

def create_compleib_models_from_template():

    lib_folder = os.path.join(core.data_path, "system_models", "_COMPleib_models")
    lib_path = os.path.join(lib_folder, "COMPleib.m")

    with open(lib_path, "r") as lib_file:
        content = lib_file.read()

    split_str = "%------------------------------------------------------------------"

    # todo: sanity check: count number of = to see if every equation was matched by regex

    content_str = content.split(split_str)[2]
    content_str = content_str.replace("\n", "")
    content_str = content_str.replace(" ", "")
    statement_list = content_str.split(";")

    # --- strategy: replace all ; inside arrays with some unique string, then we can identify statements by ..=..; ---
    array_pattern = re.compile(r"\[.+?\]")
    def replace_semicolon(matchobj):
        return matchobj.group(0).replace(";", "###")
    content_str = re.sub(array_pattern, replace_semicolon, content_str)
    # get rid of if


    statement_pattern = re.compile(r".+?;")
    statements = re.findall(statement_pattern, content_str)


    # scalar_eq_pattern = re.compile(r"[\w]+=(?!\[).+?;")
    # scalar_eq_pattern2 = re.compile(r"[\w]+=(?!\[).+?\[.+?\];")
    # matrix_eq_pattern = re.compile(r"[\w]+=\[.+?\];") # .+? is for non-greedy match


    IPS()