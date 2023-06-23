import os, sys
from ipydex import IPS
from . import core
import numpy as np
from scipy.integrate import solve_ivp, odeint
import matplotlib.pyplot as plt
import sympy as sp
import re
from ackrep_core.util import bgreen
import time
from numpy.linalg import LinAlgError

try:
    import matlab.engine
except:
    pass

row_template = "    {}s\n  {}"


def create_compleib_models_from_template(target=None):
    lib_folder = os.path.join(core.CONF.ACKREP_DATA_PATH, "system_models", "compleib_models", "_src")
    lib_path = os.path.join(lib_folder, "COMPleib.m")
    td = {"t1": {}, "t2": {}, "t3": {}, "t4": {}, "t5": {}, "t6": {}, "t7": {}, "t8": {}}
    ts = time.time()

    eng = matlab.engine.start_matlab()
    eng.cd(lib_folder)
    t1 = time.time()
    td["t1"]["t"] = t1 - ts
    td["t1"]["n"] = "matlab startup"
    with open(lib_path, "r") as lib_file:
        _content = lib_file.read()

    split_str = "%------------------------------"

    # homogenize divider
    divider_pattern = re.compile(r"\%-----+")
    content = re.sub(divider_pattern, split_str, _content)

    parts = content.split(split_str)

    t2 = time.time()
    td["t2"]["t"] = t2 - t1
    td["t2"]["n"] = "read .m and split"

    stat_dict = {"n_models": 0, "n_names": 0, "n_sources": 0}
    model_dict = {}
    model_counter = 0
    for part in parts:
        # select all comment blocks, code is handled by matlab engine
        if part[0:2] == "\n%":
            model_counter += 1
            # get model identifier (AC1)
            handle_pattern = re.compile(r"(?<=\()[\w]+(?=\))")
            handles = re.findall(handle_pattern, part)
            handle = handles[0]  # first one is model handle

            if target:
                assert isinstance(target, str), f"name {target} must be string"
                if target != handle:
                    continue
            print(f"  starting with {handle}...")
            t25 = time.time()
            td["t25"] = {}
            td["t25"]["t"] = t25 - t2
            td["t25"]["n"] = "start model"

            context = {}
            context["property"] = []
            context["not_property"] = []

            model_dict[handle] = {}
            model_dict[handle]["N"] = model_counter
            model_dict[handle]["description"] = context["description"] = make_latex_compatible(part)
            stat_dict["n_models"] += 1

            # get rid of comments inside the comment block
            ehemals_pattern = re.compile(r"\%+ehemals[ ]*\([\w]+\)")
            part = re.sub(ehemals_pattern, "", part)
            note_pattern = re.compile(r"Note:.+", re.DOTALL)
            part = re.sub(note_pattern, "", part)

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
            model_name = handle
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
                start_positions = np.ones(3) * np.inf
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
                    model_name = model_dict[ref_list[0]]["name"]
                    try:
                        source = model_dict[ref_list[0]]["source"]
                    except KeyError:
                        # reference also doesnt have a source
                        recursion_failed = True
                        core.logger.info(f"Source recursion failed for {handle}")
                else:
                    # no reference or source, but maybe the name of the previous model matches with the current model?
                    try:
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
                    except IndexError:
                        # only occurs if --only flag is set -> thats a debug case
                        pass
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

            t3 = time.time()
            td["t3"]["t"] = t3 - t25
            td["t3"]["n"] = "parse .m"
            print(row_template.format(round(t3 - t25, 1), "getting matrices..."))
            try:
                [A, B1, B, C1, C, D11, D12, D21, nx, nw, nu, nz, ny] = convert_to_numpy(
                    eng.COMPleib(handle, nargout=13)
                )
            except:
                core.logger.error(f"matlab error when reading matrices for {handle}")
                continue

            context["A_num"] = A
            context["B_num"] = B
            context["B1_num"] = B1
            context["C1_num"] = C1
            context["C_num"] = C
            context["D11_num"] = D11
            context["D12_num"] = D12
            context["D21_num"] = D21
            np.set_printoptions(threshold=sys.maxsize)
            context["A"] = "sp.Matrix(np." + repr(context["A_num"]) + ")"
            context["B"] = "sp.Matrix(np." + repr(context["B_num"]) + ")"
            context["B1"] = "sp.Matrix(np." + repr(context["B_num"]) + ")"
            context["C1"] = "sp.Matrix(np." + repr(context["C1_num"]) + ")"
            context["C"] = "sp.Matrix(np." + repr(context["C_num"]) + ")"
            context["D11"] = "sp.Matrix(np." + repr(context["D11_num"]) + ")"
            context["D12"] = "sp.Matrix(np." + repr(context["D12_num"]) + ")"
            context["D21"] = "sp.Matrix(np." + repr(context["D21_num"]) + ")"
            context["nx"] = nx
            context["nw"] = nw
            context["nu"] = nu
            context["nz"] = nz
            context["ny"] = ny
            context["model_name"] = f"'{model_name}'"
            context["creator"] = "F. Leibfritz, also see <http://www.compleib.de/>"
            context["editor"] = "This entity was automatically generated."
            context["creation_date"] = core.current_time_str()
            if source:
                context["source"] = source
            if model_counter < 10:
                key = "COM0" + str(model_counter)
            elif model_counter < 100:
                key = "COM" + str(model_counter)
            else:
                key = "CO" + str(model_counter)
            context["key"] = key

            t4 = time.time()
            td["t4"]["t"] = t4 - t3
            td["t4"]["n"] = "matlab function call"
            print(row_template.format(round(t4 - t3, 1), "simulating..."))
            # simulate model, calculate final state
            simulate_system(context)
            t5 = time.time()
            td["t5"]["t"] = t5 - t4
            td["t5"]["n"] = "simulate"
            print(row_template.format(round(t5 - t4, 1), "checking Qs, Qb ..."))
            # calculate controllability, observability
            check_qs_qb(context)
            t6 = time.time()
            td["t6"]["t"] = t6 - t5
            td["t6"]["n"] = "Qs Qb"
            print(row_template.format(round(t6 - t5, 1), "rendering..."))

            file_names = ["system_model.py", "simulation.py", "parameters.py", "metadata.yml", "documentation.tex"]
            for name in file_names:
                template_path = f"templates/{name}.template"
                folder_path = os.path.join(core.CONF.ACKREP_DATA_PATH, "system_models", "compleib_models", handle)
                if "docu" in name:
                    folder_path = os.path.join(folder_path, "_data")
                os.makedirs(folder_path, exist_ok=True)
                target_path = os.path.join(folder_path, name)
                context.pop("warning", None)
                core.render_template(template_path, context, target_path)

            t7 = time.time()
            td["t7"]["t"] = t7 - t6
            td["t7"]["n"] = "render"
            print(f"    {round(t7-t6)}s")
            print(bgreen(f"{handle} done."))
    print(stat_dict)
    print("total time:", time.time() - ts)

    # TODO: how to handle large matrices (too long for parameters.py) see CSE2


def convert_to_numpy(t: tuple) -> tuple:
    assert len(t) == 13
    a = np.array(t, dtype=object)
    for i, v in enumerate(a):
        # Matrices
        if i < 8:
            if isinstance(v, matlab.double):
                a[i] = np.array(v, dtype=float)
            else:
                # 1x1 Matrix for type conformity
                a[i] = np.array([v], dtype=float)
        # Matix dimensions
        else:
            a[i] = int(v)
    return a


def cleanup_str(s: str) -> str:
    """remove special characters and multi spaces from str"""
    for character in ["%", ":", "(", ")", ";"]:
        s = s.replace(character, "")
    s = re.sub(r"\s+", " ", s)
    return s.strip()

def make_latex_compatible(text: str):

    # Replace other special characters with appropriate LaTeX equivalents
    special_chars = {
        "&": r"\&",
        "%": r"\%",
        "$": r"\$",
        "#": r"\#",
        "_": r"\_",
        "{": r"\{",
        "}": r"\}",
        "<": r"\textless{}",
        ">": r"\textgreater{}",
    }
    
    for char, latex_equiv in special_chars.items():
        text = text.replace(char, latex_equiv)
    
    return text.strip()


def simulate_system(context: dict):
    """simulate COMPleib system model and add relevnat infos to context dict"""

    def uu_rhs(t, x):
        u = np.zeros(context["nu"])
        # u[0] = sp.sin(t)
        return u

    def rhs(t, x):
        u = uu_rhs(t, x)
        w = np.zeros(context["nw"])

        dxx_dt = np.matmul(context["A_num"], x) + np.matmul(context["B1_num"], w) + np.matmul(context["B_num"], u)

        return dxx_dt

    t_end = context["t_end"] = 10
    steps = context["steps"] = 1000

    if context["nx"] > 100:
        # TODO simulation takes too long
        context["final_state"] = f"np.zeros({context['nx']})"
        core.logger.warning(f"Simulation of {context['model_name']} skipped.")
        return

    xx0 = np.ones(context["nx"])
    tt = np.linspace(0, t_end, steps)

    res = solve_ivp(rhs, (0, t_end), xx0, t_eval=tt)
    context["final_state"] = "np." + repr(res.y[:, -1])

    # res = odeint(rhs, y0=xx0, t=tt, tfirst=True)
    # context["final_state"] = "np." + repr(res[-1, :])

    return


def check_qs_qb(context: dict):
    """check controllability and observability of model using Hautus criteria. Add info to context"""
    if context["nx"] > 500:
        # TODO calculation takes too long
        core.logger.warning(f"Qs, Qb of {context['model_name']} skipped.")
        return

    A = context["A_num"]
    B = context["B_num"]
    C = context["C1_num"]
    nx = context["nx"]

    # hautus
    ev_A = np.linalg.eig(A)[0]
    controllable = True
    for ev in ev_A:
        mat = np.concatenate((ev * np.eye(nx) - A, B), axis=1, dtype=complex)
        if np.linalg.matrix_rank(mat) != nx:
            controllable = False
            break
    if controllable:
        context["property"].append('I7864["controllability"]')
    else:
        context["not_property"].append('I7864["controllability"]')

    observable = True
    for ev in ev_A:
        mat = np.concatenate((ev * np.eye(nx) - A, C), axis=0, dtype=complex)
        if np.linalg.matrix_rank(mat) != nx:
            observable = False
            break
    if observable:
        context["property"].append('I3227["observability"]')
    else:
        context["not_property"].append('I3227["observability"]')

    # kalman
    # Qs = np.copy(B)
    # Ai = np.eye(nx)
    # for i in range(1, nx):
    #     Ai = np.matmul(Ai, A)
    #     Qs = np.concatenate((Qs, np.matmul(Ai, B)), axis=1, dtype=float)
    # try:
    #     r_qs = np.linalg.matrix_rank(Qs)
    #     if r_qs == nx:
    #         context["property"].append('I7864["controllability"]')
    #     else:
    #         context["not_property"].append('I7864["controllability"]')
    # except LinAlgError:
    #     core.logger.warning(f"rank calculation of controllability matrix failed")

    # Qb = np.copy(C)
    # Ai = np.eye(nx)
    # for i in range(1, nx):
    #     Ai = np.matmul(Ai, A)
    #     Qb = np.concatenate((Qb, np.matmul(C, Ai)), axis=0, dtype=float)
    # try:
    #     r_qb = np.linalg.matrix_rank(Qb)
    #     if r_qb == nx:
    #         context["property"].append('I3227["observability"]')
    #     else:
    #         context["not_property"].append('I3227["observability"]')
    # except LinAlgError:
    #     core.logger.warning(f"rank calculation of observability matrix failed")

    return
