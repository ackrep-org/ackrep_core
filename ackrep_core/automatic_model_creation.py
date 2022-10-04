import os
from ipydex import IPS
from . import core
import numpy as np
from scipy.integrate import solve_ivp
import matplotlib.pyplot as plt
import matlab.engine
import sympy as sp

def create_compleib_models_from_template():

    lib_folder = os.path.join(core.data_path, "system_models", "_COMPleib_models")
    lib_path = os.path.join(lib_folder, "COMPleib.m")

    with open(lib_path, "r") as lib_file:
        content = lib_file.read()

    split_str = "%------------------------------------------------------------------"

    # todo: sanity check: count number of = to see if every equation was matched by regex

    # content_str = content.split(split_str)[2]
    # content_str = content_str.replace("\n", "")
    # content_str = content_str.replace(" ", "")
    # statement_list = content_str.split(";")

    # # --- strategy: replace all ; inside arrays with some unique string, then we can identify statements by ..=..; ---
    # array_pattern = re.compile(r"\[.+?\]")
    # def replace_semicolon(matchobj):
    #     return matchobj.group(0).replace(";", "###")
    # content_str = re.sub(array_pattern, replace_semicolon, content_str)
    # # get rid of if


    # statement_pattern = re.compile(r".+?;")
    # statements = re.findall(statement_pattern, content_str)


    # scalar_eq_pattern = re.compile(r"[\w]+=(?!\[).+?;")
    # scalar_eq_pattern2 = re.compile(r"[\w]+=(?!\[).+?\[.+?\];")
    # matrix_eq_pattern = re.compile(r"[\w]+=\[.+?\];") # .+? is for non-greedy match


    eng = matlab.engine.start_matlab()

    eng.cd(lib_folder)
    [A,B1,B,C1,C,D11,D12,D21,nx,nw,nu,nz,ny] = convert_to_numpy(eng.COMPleib("AC1", nargout=13))

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
    
    file_names = ["system_model", "simulation", "parameters"]

    for name in file_names:
        template_path = f'templates/{name}.py.template'
        target_path = os.path.join(core.data_path, "system_models", "test_entity", f"{name}.py")
        core.render_template(template_path, context, target_path)
   

def convert_to_numpy(t: tuple) -> tuple:
    a = np.array(t)
    for i, v in enumerate(a):
        if isinstance(v, matlab.double):
            a[i] = np.array(v)
        elif isinstance(v, float) and v == int(v):
            a[i] = int(v)
    return a

