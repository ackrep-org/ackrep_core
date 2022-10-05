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
        content = lib_file.read()

    split_str = "%------------------------------------------------------------------"
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
            handle = re.findall(handle_pattern, part)[0]  # take first
            model_dict[handle] = {}
            model_dict[handle]["N"] = model_counter
            model_dict[handle]["description"] = cleanup_str(part)
            stat_dict["n_models"] += 1

            recursion_failed = False

            # find source
            # author pattern and everything after, 
            source = None
            source_pattern = re.compile(r"((?<=\s)[A-Z]\.\s[A-Z][a-z]+.+)|(?<=\()see Leibfritz.+(?=\))", re.DOTALL)  
            sources = re.findall(source_pattern, part)
            if len(sources) > 0:
                assert len(sources) == 1, "only one source should be matched here"
                source = cleanup_str(sources[0])
            else:
                # no source was found, check for internal reference, inicated by "version of", "see", "like"
                raw = r"(?<=version of \()[\w]+(?=\))|(?<=see \()[\w]+(?=\))|(?<=like \()[\w]+(?=\))"
                reference_pattern = re.compile(raw) 
                ref_list = re.findall(reference_pattern, part)
                if ref_list:
                    assert len(ref_list) == 1
                    try:
                        source = model_dict[ref_list[0]]["source"]
                        flags["ref_model"] = ref_list[0]
                    except KeyError:
                        recursion_failed = True
                        core.logger.info(f"Source recursion failed for {handle}")
            if source:
                model_dict[handle]["source"] = source
            else:
                stat_dict["n_sources"] += 1
                if not recursion_failed:
                    core.logger.warning(f"no Source found for {handle}")
                    # IPS()
                    
            # try to find appropriate model name
            if "source" in model_dict[handle].keys() and "ref_model" not in flags.keys():
                # everything between handle and source is name
                name_pattern = re.compile(r"(?<=\):[ ]).+?(?=[A-Z]\.\s[A-Z][a-z]+|\(see Leibfritz)", re.DOTALL)
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
            else:
                pat = re.compile(r"(?<=\): ).+", re.DOTALL)
                model_name = cleanup_str(re.findall(pat, part)[0])

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
            # IPS()
    # TODO:
    # - WEC1 source problem
    print(stat_dict)
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
    s = re.sub(r"\s+", " ", s)
    return s