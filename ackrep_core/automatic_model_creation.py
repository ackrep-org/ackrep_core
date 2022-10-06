import os
from ipydex import IPS
from . import core
import numpy as np
from scipy.integrate import solve_ivp
import matplotlib.pyplot as plt
import matlab.engine
import sympy as sp
import re
from util import run_command

def create_compleib_models_from_template():

    lib_folder = os.path.join(core.data_path, "system_models", "_COMPleib_models")
    lib_path = os.path.join(lib_folder, "COMPleib.m")

    eng = matlab.engine.start_matlab()
    eng.cd(lib_folder)

    with open(lib_path, "r") as lib_file:
        _content = lib_file.read()
    
    split_str = "%------------------------------"

    # homogenize divider
    divider_pattern = re.compile(r"\%-----+")
    content = re.sub(divider_pattern, split_str, _content)

    parts = content.split(split_str)

    stat_dict = {"n_models": 0, "n_names": 0, "n_sources": 0}
    model_dict = {}
    model_counter = 0
    for part in parts:
        # select all comment blocks, code is handled by matlab engine
        if part[0:2] == "\n%":
            # flags = {}
            # get rid of comments inside the comment block
            ehemals_pattern = re.compile(r"\%+ehemals[ ]*\([\w]+\)")
            part = re.sub(ehemals_pattern, "", part)
            note_pattern = re.compile(r"Note:.+", re.DOTALL)
            part = re.sub(note_pattern, "", part)

            # get model identifier (AC1)
            handle_pattern = re.compile(r"(?<=\()[\w]+(?=\))")
            handles = re.findall(handle_pattern, part)
            handle = handles[0]  # first one is model handle
            model_dict[handle] = {}
            model_dict[handle]["N"] = model_counter
            model_dict[handle]["description"] = cleanup_str(part)
            stat_dict["n_models"] += 1

            recursion_failed = False

            """
            strategy to parse heterogeneous comment blocks:
            - check if source exists (year and "")
                - yes: extract source (can be structured in various ways), name = everything before source
                - no: check if internal reference exists, e.g. see (AC1)
                    - yes: use name and source of reference
                    - no: everything is name, there is no source
            """
            source = None
            year_pattern = re.compile(r"(?:20|19)[0-9]{2}")
            title_pattern = re.compile(r'".+?"', re.DOTALL)
            author_pattern = re.compile(r"[A-Z]\. (?:[A-Z]\. )?.+?(?=and|,|:)")
            leibfritz_pattern = re.compile(r"Leibfritz, Volkwein:")

            indicator = 0
            for pattern in [year_pattern, title_pattern, author_pattern, leibfritz_pattern]:
                if re.findall(pattern, part):
                    indicator += 1

            if indicator >= 1:
                # find the earliest possible start of the source
                # source could start with title '"..."', author 'M. [M.] Mustermann' or 'see Leibfritz, Volkwein:'
                start_positions = np.ones(3)*np.inf
                for i, pattern in enumerate([title_pattern, author_pattern, leibfritz_pattern]):
                    s = [match.start(0) for match in re.finditer(pattern, part)]
                    if s:
                        start_positions[i] = s[0]
                start = int(min(start_positions))

                source = cleanup_str(part[start:])
                begin = part[:start]
                raw = r"(?<=\(" + handle + r"\)).+"
                name_pattern = re.compile(raw, re.DOTALL)
                model_name = cleanup_str(re.findall(name_pattern, begin)[0])
                if len(model_name) < 3:
                    # model has no name
                    model_name = handle
            else:
                # no source was found, check for internal reference handle
                ref_list = re.findall(handle_pattern, part.split(f"({handle})", 1)[-1])
                if ref_list:
                    assert len(ref_list) == 1
                    try:
                        source = model_dict[ref_list[0]]["source"]
                        model_name = model_dict[ref_list[0]]["name"]
                    except KeyError:
                        # reference also doesnt have a source
                        recursion_failed = True
                        core.logger.info(f"Source recursion failed for {handle}")
                else:
                    # no reference or source, but maybe the name of the previous model matches with the current model?
                    prev_handle = list(model_dict.keys())[-2]
                    prev_name = model_dict[prev_handle]["name"]
                    if prev_name.lower() in part.lower():
                        model_name = model_dict[prev_handle]["name"]
                        if "source" in model_dict[prev_handle].keys():
                            source = model_dict[prev_handle]["source"]
                    else:
                        raw = r"(?<=\(" + handle + r"\)).+"
                        name_pattern = re.compile(raw, re.DOTALL)
                        model_name = cleanup_str(re.findall(name_pattern, part)[0])
            if source:
                model_dict[handle]["source"] = source
                stat_dict["n_sources"] += 1
            else:
                if not recursion_failed:
                    core.logger.warning(f"no Source found for {handle}")
                    # IPS()
 
            model_dict[handle]["name"] = model_name
            if model_name == handle:
                core.logger.warning(f"no model name found for {handle}")
                # IPS()
            else:
                stat_dict["n_names"] += 1

            model_counter += 1
            def p():
                print(handle)
                print(model_name)
                print(source)

    print(stat_dict)
    IPS()
    exit()

    [A,B1,B,C1,C,D11,D12,D21,nx,nw,nu,nz,ny] = convert_to_numpy(eng.COMPleib(handle, nargout=13))

    context = {}
    context["A"] = "sp." + str(sp.Matrix(A))
    context["B"] = "sp." + str(sp.Matrix(B))
    context["B1"] = "sp." + str(sp.Matrix(B1))
    context["C"] = "sp." + str(sp.Matrix(C))
    context["D21"] = "sp." + str(sp.Matrix(D21))
    context["nx"] = nx
    context["nw"] = nw
    context["nu"] = nu
    context["nz"] = nz
    context["ny"] = ny
    context["model_name"] = "'AC1'"
    model_counter = 1
    if model_counter < 10:
        key = "COM0" + str(model_counter)
    else:
        key = "COM" + str(model_counter)
    context["key"] = key
    
    file_names = ["system_model.py", "simulation.py", "parameters.py", "metadata.yml"]

    for name in file_names:
        template_path = f'templates/{name}.template'
        target_path = os.path.join(core.data_path, "system_models", "test_entity", name)
        core.render_template(template_path, context, target_path)


def convert_to_numpy(t: tuple) -> tuple:
    a = np.array(t)
    for i, v in enumerate(a):
        if isinstance(v, matlab.double):
            a[i] = np.array(v)
        elif isinstance(v, float) and v == int(v):
            a[i] = int(v)
    return a

def cleanup_str(s: str) -> str:
    """remove % and multi spaces from str"""
    for character in ["%", ":", "(", ")"]:
        s = s.replace(character, "")
    s = re.sub(r"\s+", " ", s)
    return s.strip()