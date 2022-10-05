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
            flags = {}
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

            # find source
            # author pattern and everything after, 
            source = None
            author_pattern = re.compile(r"(?<=\s)[A-Z]\.\s[A-Z][a-z]+.+|(?<=\()see Leibfritz.+(?=\))", re.DOTALL)  
            sources = re.findall(author_pattern, part) # this is prefered, since it captures the source as a whole

            year_pattern = re.compile(r"[1-2][0-9]{3}")
            years = re.findall(year_pattern, part) # this is the fallback, it just indicates, that there is a source

            if sources:
                assert len(sources) == 1, "only one source should be matched here"
                assert len(sources[0]) > 0, "dont match empty strings"
                source = cleanup_str(sources[0])
            elif years and part.count('"') == 2:
                # there is a source, but it doesnt match the pattern above -> speacial handling for source and name
                s_pat = re.compile(r"(?<=\n).+", re.DOTALL)
                source = cleanup_str(re.findall(s_pat, part.split(f"({handle})", 1)[-1])[0])
                flags["special"] = True
            else:
                # no source was found, check for internal reference handle
                ref_list = re.findall(handle_pattern, part.split(f"({handle})", 1)[-1])
                if ref_list:
                    assert len(ref_list) == 1
                    try:
                        source = model_dict[ref_list[0]]["source"]
                        flags["ref_model"] = ref_list[0]
                    except KeyError:
                        recursion_failed = True
                        core.logger.info(f"Source recursion failed for {handle}")
                else:
                    # no reference or source, but maybe the name of the previous model matches with the current model?
                    prev_handle = list(model_dict.keys())[-2]
                    prev_name = model_dict[prev_handle]["name"]
                    if prev_name.lower() in part.lower() and "source" in model_dict[prev_handle].keys():
                        source = model_dict[prev_handle]["source"]
                        flags["ref_model"] = prev_handle

            if source:
                model_dict[handle]["source"] = source
                stat_dict["n_sources"] += 1
            else:
                if not recursion_failed:
                    core.logger.warning(f"no Source found for {handle}")
                    # IPS()
                    
            # try to find appropriate model name
            if "source" in model_dict[handle].keys() and "ref_model" not in flags.keys() and "special" not in flags.keys():
                # everything between handle and source is name
                raw = r"(?<=\(" + handle + r"\)).+?(?=[A-Z]\.\s[A-Z][a-z]+|\(see Leibfritz)"
                name_pattern = re.compile(raw, re.DOTALL)
                model_names = re.findall(name_pattern, part)
                if len(model_names) > 0:
                    assert len(model_names) == 1
                    model_name = cleanup_str(model_names[0])
                    if len(model_name) < 5:
                        # re probably detected a first name of an author
                        model_name = handle
                else:
                    model_name = handle
            elif "ref_model" in flags.keys():
                # if this is just a slightly diffrent version, use name of original model
                model_name = model_dict[flags["ref_model"]]["name"]
            elif "special" in flags.keys():
                raw = r"(?<=\(" + handle + r"\)).+?(?=\n)" 
                name_pattern = re.compile(raw)
                model_name = cleanup_str(re.findall(name_pattern, part)[0])
            else:
                raw = r"(?<=\(" + handle + r"\)).+"
                name_pattern = re.compile(raw, re.DOTALL)
                model_name = cleanup_str(re.findall(name_pattern, part)[0])

            model_dict[handle]["name"] = model_name
            if model_name == handle:
                core.logger.warning(f"no model name found for {handle}")
                IPS()
            else:
                stat_dict["n_names"] += 1

            model_counter += 1
            def p():
                print(handle)
                print(model_name)
                print(source)
            # IPS(handle == "ROC3")
    # TODO NN1, DIS5 better pattern for authors
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
    s = s.replace("%", "")
    s = s.replace(":", "")
    s = re.sub(r"\s+", " ", s)
    return s.strip()