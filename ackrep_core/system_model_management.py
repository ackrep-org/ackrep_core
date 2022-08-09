"""
Core module of GenericModel

Created on Wed Jun  9 13:33:34 2021
@author: Jonathan Rockstroh
"""

import importlib
import sympy as sp
import numpy as np
import tabulate as tab
import warnings
import abc
import sys
import os
import subprocess
import matplotlib.pyplot as plt
import inspect

from . import core
from .util import root_path, run_command
from . import models
from ipydex import IPS


class GenericModel:
    t_symb = sp.Symbol("t")

    def __init__(self, x_dim=None, u_func=None, pp=None):
        """
        GenericModel provides an enviroment for the work with model which
        consist of a system of ODEs. GenericModel is meant to be used as
        abstract class.

        In the implementation of the concrete model:
            The system of ODEs shall be written in the function
            "get_rhs_symbolic" as symbolic functions. The used symbolic
            parameters in the model must be the key-entries from self.pp_dict.

            A default input function shall be written in the function
            "uu_default_function".

        The function "get_rhs_func" takes the symbolic function from
        "get_rhs_symbolic" and converts it to an executable function
        with sympy.lambdify. It uses the parameter set, which is present at
        the time of executing the function.


        Parameters:
        ==========
        x_dim : positive int
            Dimension of the state vector of the model
            Only has an effect for extendible systems (e.g. N-Integrator).
            For non-extenible systems it hasn't any effect.'

        u_func : callable
        Individual input function for the model.
            u_func shall take two parameters :
                t : scalar or list
                    scalar: time at which the input function shall be
                            evaluated
                    list: times at which the input function shall be evaluated

                xx_nv : list or list of lists
                    list: state vector of the model at time t
                    list of lists: state vectors of the model at the times in t

            u_func shall return :
                list: input vector uu at time t
                list of lists: input vectors at the times in t


        pp : list[float] or dict{sympy.symbol:float}
            Parameters of the model.
            if pp=None (default) then values from parameters.py are used

        Notes:
        =====
        The dimension of an existing model-object can't be changed.
        The parameters and input function of an existing model-object
        can be changed.

        """

        self.sys_dim = x_dim
        self.default_param_sys_dim = None

        self.initialize()

        if x_dim is None and self.sys_dim is None:
            self.sys_dim = self.default_param_sys_dim

        assert isinstance(self.sys_dim, int), "not defined variable 'sys_dim'"

        # Initialize all Parameters of the Model-Object with None
        # System Dimension
        self.n = None
        # Symbolic State Vector
        self.xx_symb = None
        # Symbolic Input Vector
        self.uu_symb = None
        # Symbolic combined vector
        self._xxuu_symb = None
        # Symbolic rhs-vector (first derivative)
        self.dxx_dt_symb = None
        # Symbolic parameter vector
        self.pp_symb = None
        # Parameter dictionary with symbol:value entries
        self.pp_dict = None
        # Parameter dictionary with str(symbol):value entries
        self.pp_str_dict = None
        # Parameter Substitution List for sp.subs methods
        self.pp_subs_list = None
        # Input function
        self.uu_func = None

        try:
            self.params.get_default_parameters()
        except AttributeError:
            self.has_params = False

        # Set self.n
        self._set_dimension(self.sys_dim)
        # Create symbolic input vector
        self._create_symb_uu(self.u_dim)
        # Create symbolic xx and xxuu
        self._create_symb_xx_xxuu()
        # Create parameter dict, subs_list and symbolic parameter vector
        self.set_parameters(pp)
        # Create a dict like self.pp_dict but with strings as keys instead of symbols.
        self._create_pp_str_dict()
        # Create Symbolic parameter vector and subs list
        self._create_symb_pp()
        # Create Substitution list
        self._create_subs_list()

        # choose input function
        if self.u_dim == 0:
            self.set_input_func(self.uu_autonomous_func())
        else:
            assert hasattr(
                self, "uu_default_func"
            ), f"Your system has an input dimension of {self.u_dim} but no method 'uu_default_func'."
            self.set_input_func(self.uu_default_func())
            if u_func is not None:
                self.set_input_func(u_func)

    # ----------- SET NEW INPUT FUNCTION ---------- #
    # --------------- Only for non-autonomous Systems

    def set_input_func(self, u_func):
        """
        Assignes an individually written function as input function for the
        model.

        Parameters
        ==========
        u_func : callable object
            The function which shall be used as input function for the model.

            u_func shall take two parameters :
                t : scalar or list
                    scalar: time at which the input function shall be
                            evaluated
                    list: times at which the input function shall be evaluated

                xx_nv : list or list of lists
                    list: state vector of the model at time t
                    list of lists: state vectors of the model at the times in t

            u_func shall return :
                list: input vector uu at time t
                list of lists: input vectors at the times in t

        """
        # check if u_func is a callable object
        assert callable(u_func), ":param u_func: isn't a callable object."
        # assign given function to object variable
        self.uu_func = u_func

    # ----------- SET DEFAULT INPUT FUNCTION ---------- #
    # --------------- Only for non-autonomous Systems
    # --------------- MODEL DEPENDENT

    def uu_autonomous_func(self):
        """define a input function for autonomous systems"""

        def uu_rhs(t, xx_nv):
            return []

        return uu_rhs

    # ----------- SET STATE VECTOR DIMENSION ---------- #

    def _set_dimension(self, x_dim):
        """
        :param dim:(int > 0), Order of the system
        """
        # check if system is n-extendable
        if self.n is not None:
            warnings.warn(
                'Function "set_dimension" had no effect. \
                          System is not n-extendable.'
            )
            return
        # check if :param dim: is valid -- ADJUSTION NEEDED IN SPECIAL CASES
        assert x_dim > 0 and isinstance(x_dim, int), "Param: x_dim isn't valid."
        self.n = x_dim

    # ----------- CREATE INDIVIDUAL PARAMETER DICT  ---------- #

    def _create_individual_p_dict(self, pp, pp_symb=None):
        """
        Function which creates the parameter dict, in case that individual
        parameters are given to the model.

        :param pp: (list(float) or dict{sympy.symbol:float}) parameters
        :param pp_symb: list(sympy.symbol) symbolic parameters
        """
        # Check if pp is a dictionary type object
        if isinstance(pp, dict):
            p_values = list(pp.values())
            # Take Keys in the dict as parameter symbols
            self.pp_symb = list(pp.keys())
            assert isinstance(self.pp_symb, sp.Symbol), "param pp: keys aren't of type sp.Symbol"
            self.pp_dict = pp
        else:  # --> pp is a list type object
            assert (
                pp_symb is not None
            ), "pp_symb is expected not to be None, \
                                    because pp is not a dict type object"
            # Define symbolic parameter vector
            self.pp_symb = pp_symb
            # create parameter dict
            parameter_number = len(pp_symb)
            self.pp_dict = {self.pp_symb[i]: pp[i] for i in range(parameter_number)}

    # ----------- SYMBOLIC RHS FUNCTION ---------- #
    # --------------- MODEL DEPENDENT

    @abc.abstractmethod
    def get_rhs_symbolic(self):
        """
        Creates the right-hand-sides of the ODEs as symbolic sympy expressions.

        .. important ::
            It must use the symbolic variables from:
            self.xx_symb, self.uu_symb, self.pp_symb

        :return:(list) symbolic rhs-functions
        """

    # ----------- Init ---------- #
    # --------------- MODEL DEPENDENT

    @abc.abstractmethod
    def initialize(self):
        """
        init
        """

    # ------ SYMBOLIC RHS FUNCTION WITH NUMERICAL PARAMETERS ---------- #
    # --------------- MODEL INDEPENDENT

    def get_rhs_symbolic_num_params(self, params=None):
        """
        Create symbolic function of the model with the parameter values.

        :params:(dict) parameter to substitute
        :return:(matrix) matrix with right hand side symbolic functions with parameters
        """
        # create symbolic matrix
        rhs_symb = sp.Matrix(self.get_rhs_symbolic())
        # substitute parameters with numerical values
        self._create_subs_list()
        rhs_symb_num_params = sp.Matrix(rhs_symb.subs(self.pp_subs_list))

        return rhs_symb_num_params

    # ----------- NUMERIC RHS FUNCTION ---------- #
    # -------------- MODEL INDEPENDENT - no adjustion needed

    def get_rhs_func(self):
        """
        Creates an executable function of the model which uses:
            - the current parameter values
            - the current input function

        To evaluate the effect of a changed parameter set a new rhs_func needs
        to be created with this method.

        :return:(function) rhs function for numerical solver like
                            scipy.solve_ivp
        """

        dxx_dt_func = self.get_rhs_symbolic_num_params()
        # Create executable rhs function
        dxx_dt_func = sp.lambdify(self._xxuu_symb, list(dxx_dt_func), modules="numpy")
        # create rhs function
        def rhs(t, xx_nv):
            """
            :param t:(tuple or list) Time
            :param xx_nv:(self.n-dim vector) numerical state vector
            :return:(self.n-dim vector) first time derivative of state vector
            """
            uu_nv = self.uu_func(t, xx_nv)

            # combine numerical state and input vector
            xxuu_nv = tuple(xx_nv) + tuple(uu_nv)
            # evaluate function
            dxx_dt_nv = dxx_dt_func(*xxuu_nv)

            return dxx_dt_nv

        return rhs

    # ----------- CREATE SYMBOLIC INPUT VECTOR ---------- #

    def _create_symb_uu(self, u_dim):
        self.uu_symb = [sp.Symbol("u" + str(i + 1)) for i in range(0, self.u_dim)]

    # ----------- CREATE SYMBOLIC STATE AND COMBINED VECTOR ---------- #

    def _create_symb_xx_xxuu(self):
        # create new symbolic state vector
        self.xx_symb = [sp.Symbol("x" + str(i + 1)) for i in range(0, self.n)]
        self._xxuu_symb = self.xx_symb + self.uu_symb

    # ----------- CREATE SYMBOLIC PARAMETER VECTOR ---------- #

    def _create_symb_pp(self, symb_pp_list=None):
        if symb_pp_list is not None:
            assert isinstance(symb_pp_list, list), ":param symb_pp_list: is not a list type object"
            self.pp_symb = symb_pp_list
            return

        if self.pp_dict is None:
            return
        self.pp_symb = list(self.pp_dict.keys())

    # ----------- CREATE PARAMETER SUBSTITUTION LIST ---------- #

    def _create_subs_list(self):
        if self.pp_dict is None:
            self.pp_subs_list = []
            return
        self.pp_subs_list = list(self.pp_dict.items())

    # ----------- SET_PARAMETERS ---------- #

    def set_parameters(self, pp):
        """
        :param pp:(vector or dict-type with floats>0) parameter values
        :param x_dim:(positive int)
        """
        # Case: System doesn't have parameters
        if not self.has_params:
            return

        # Case: No symbolic parameters created
        if self.pp_symb is None:
            try:
                symb_pp = self._create_n_dim_symb_parameters()
            except AttributeError:  # To ensure compatibility with old classes
                symb_pp = None
            # Check if system has constant dimension
            if symb_pp is None:
                symb_pp = list(self.params.get_default_parameters().keys())
            self._create_symb_pp(symb_pp)

        # Case: Use Default Parameters
        if pp is None:
            pp_dict = self.params.get_default_parameters()
            # Check if a possibly given system dimension fits to the default
            # parameter length
            assert len(self.pp_symb) == len(pp_dict), (
                "Expected :param pp: to be given, because the amount of \
                    parameters needed ("
                + str(len(self.pp_symb))
                + ") \
                    for the system of given dimension ("
                + str(self.n)
                + ") \
                    doesn't fit to the number of default parameters ("
                + str(len(pp_dict))
                + ")."
            )
            self.pp_dict = pp_dict
            return

        # Check if pp is list or dict type
        assert isinstance(pp, dict) or isinstance(pp, list), ":param pp: must be a dict or list type object"

        # Case: Individual parameter (list or dict type) variable is given
        if pp is not None:
            # Check if pp has correct length
            assert len(self.pp_symb) == len(pp), (
                ":param pp: Given Dimension: " + str(len(pp)) + ", Expected Dimension: " + str(len(self.pp_symb))
            )
            # Case: parameter dict ist given -> individual parameter symbols
            # and values
            if isinstance(pp, dict):
                self._create_individual_p_dict(pp)
                return
            # Case: Use individual parameter values
            else:
                self._create_individual_p_dict(pp, self.pp_symb)
                return

        # Case: Should never happen.
        raise Exception("Critical Error: Check Source Code of set_parameters.")

    def _create_pp_str_dict(self) -> None:
        """
        Create a dict like self.pp_dict but with strings as keys instead of symbols.
        """
        # in case of models without params
        if self.pp_dict is None:
            return
        self.pp_str_dict = dict([(str(key), value) for key, value in self.pp_dict.items()])

    def get_parameter_value(self, p_str):
        value = self.pp_str_dict[p_str]
        return value


def save_plot_in_dir(name="plot.png"):
    """
    inspect, where call is coming from, then save plot in corresponding directory
    """
    caller_frame = inspect.currentframe().f_back
    file_name = inspect.getframeinfo(caller_frame)[0]
    path = os.path.split(file_name)[0]

    plot_dir = os.path.join(path, "_data")
    if not os.path.isdir(plot_dir):
        os.mkdir(plot_dir)
    plt.savefig(os.path.join(plot_dir, name), dpi=96 * 2)


### Parameter fetching and tex-ing ###


def update_parameter_tex(key):
    """search for parameter file of system_model key
    update tex files and pdf w.r.t. parameters.py
    delete auxiliary files
    """
    parameters = import_parameters(key)

    # ------ CREATE RAMAINING PART OF THE LATEX TABULAR AND WRITE IT TO FILE
    # Define "Symbol" column
    pp_dict_key_list = list(parameters.get_default_parameters().keys())
    p_symbols = [
        sp.latex(pp_dict_key_list[i], symbol_names=parameters.latex_names)
        for i in range(len(parameters.get_default_parameters()))
    ]
    # set cells in math-mode
    for i in range(len(p_symbols)):
        p_symbols[i] = "$" + p_symbols[i] + "$"

    # Define "Value" column
    p_values = [sp.latex(p_sf) for p_sf in parameters.pp_sf]
    # set cells in math-mode
    for i in range(len(p_values)):
        p_values[i] = "$" + p_values[i] + "$"

    # Define "Range" column
    p_ranges = []
    if hasattr(parameters, "pp_range_list"):
        for r in parameters.pp_range_list:
            # get interval boundaries
            if isinstance(r, list):
                ib = ["[", "]"]
                p_ranges.append(f"${ib[0]}{r[0]}, {r[1]}{ib[1]}$")
            elif isinstance(r, tuple):
                ib = ["(", ")"]
                p_ranges.append(f"${ib[0]}{r[0]}, {r[1]}{ib[1]}$")
            elif isinstance(r, str) and len(r) == 1:
                p_ranges.append("$\mathbb{" + r + "}$")
            elif r is None:
                # used for fixed parameters, such as g = 9.81
                p_ranges.append("-")
            else:
                p_ranges.append("$\mathbb{R}$")
            # replace inf
            p_ranges[-1] = p_ranges[-1].replace("inf", "\infty")

        # Create list, which contains the content of the table body
        table_body_list = np.array(
            [*parameters.start_columns_list, p_symbols, p_values, p_ranges, *parameters.end_columns_list]
        )
        if "Range" not in parameters.tabular_header:
            parameters.tabular_header.extend("Range")

    else:
        # for backwards compatibility
        # Create list, which contains the content of the table body
        table_body_list = np.array([*parameters.start_columns_list, p_symbols, p_values, *parameters.end_columns_list])

    # Convert list of column entries to list of row entries
    table = table_body_list.transpose()

    # Create string which contains the latex-code of the tabular
    tex = tab.tabulate(table, parameters.tabular_header, tablefmt="latex_raw", colalign=parameters.col_alignment)

    # Change Directory to the Folder of the Model.
    cwd = os.path.dirname(os.path.abspath(__file__))
    parent2_cwd = os.path.dirname(os.path.dirname(cwd))
    path_base = os.path.join(root_path, parameters.base_path, "_data")
    os.chdir(path_base)
    # Write tabular to Parameter File.
    file = open("parameters.tex", "w")
    file.write(tex)
    file.close()

    return 0


def create_pdf(key, output_path=None):
    """create new documentation.pdf from documentation.tex and parameters.tex, specified by key.
    If outputpath is set, pdf is created at given path.
    Auxiliary Files are deleted.
    """
    system_model_entity = core.model_utils.get_entity(key)
    base_path = system_model_entity.base_path
    tex_path = os.path.join(root_path, base_path, "_data")
    os.chdir(tex_path)
    if output_path is None:
        res = run_command(["pdflatex", "-halt-on-error", "documentation.tex"], logger=core.logger, capture_output=True)
    else:
        test_dir = os.path.join(tex_path, output_path)
        if not os.path.isdir(test_dir):
            os.mkdir(test_dir)
        res = run_command(
            ["pdflatex", "-halt-on-error", "-output-directory", output_path, "documentation.tex"],
            logger=core.logger,
            capture_output=True,
        )

    # clean up auxiliary files
    import time

    time.sleep(5)

    delete_list = ["gz", "aux", "fdb_latexmk", "fls", "log", "out"]

    # no specified output directory
    if output_path is None:
        file_path = tex_path
    # absolute output directory
    elif os.path.isabs(output_path):
        file_path = output_path
    # relative output directory
    else:
        file_path = os.path.join(tex_path, output_path)

    os.chdir(file_path)
    files = os.listdir()
    for file in files:
        if file.split(".")[-1] in delete_list:
            os.remove(os.path.split(file)[1])

    return res


def import_parameters(key=None):
    """import parameters.py selected by given key and create related get function for system_model
    if key is None, the caller frame is inpected to get its location (used by system_model.py (ackrep_data))

    Args:
        key: key of system_model

    Returns:
        module: parameters
    """
    if key == None:
        # get caller frame -> location of file
        frame = inspect.currentframe()
        prev_frame = frame.f_back
        file_name = inspect.getframeinfo(prev_frame)[0]
        path = os.path.split(file_name)[0]
        yml_path = os.path.join(path, "metadata.yml")
        key = core.get_metadata_from_file(yml_path)["key"]

    sys.path.insert(0, root_path)

    system_model_entity = core.model_utils.get_entity(key)
    base_path = system_model_entity.base_path
    mod_path = os.path.join(base_path, "parameters")
    if not os.path.isfile(os.path.join(root_path, base_path, "parameters.py")):
        raise FileNotFoundError(f"Import of parameters.py failed. Path {base_path} does not lead to parameters.py.")
    mod_path = ".".join(mod_path.split(os.path.sep))

    core.logger.debug(f"loading parameters for key {key} from {mod_path}")

    parameters = importlib.import_module(mod_path)
    importlib.reload(parameters)  # reload module to ensure most recent version
    parameters.base_path = base_path

    parameters.parameter_check = check_system_parameters(parameters)
    assert parameters.parameter_check == 0, "Parameter file of system model is missing mandatory attributes!"

    pp_nv = list(sp.Matrix(parameters.pp_sf).subs(parameters.pp_subs_list))
    pp_dict = {parameters.pp_symb[i]: pp_nv[i] for i in range(len(parameters.pp_symb))}

    def get_default_parameters():
        return pp_dict

    def get_symbolic_parameters():
        return parameters.pp_symb

    parameters.get_default_parameters = get_default_parameters
    parameters.get_symbolic_parameters = get_symbolic_parameters

    # check if parameters are inside suggested ranges
    if hasattr(parameters, "pp_range_list"):
        msg = "Dimension Mismatch between parameters and respective ranges."
        assert len(parameters.pp_range_list) == len(parameters.get_default_parameters()), msg
        for i, (p, v) in enumerate(pp_dict.items()):
            warn = False
            low, high = parameters.pp_range_list[i]
            if isinstance(parameters.pp_range_list[i], list):
                if not (low <= v and v <= high):
                    warn = True
            elif isinstance(parameters.pp_range_list[i], tuple):
                if not (low < v and v < high):
                    warn = True

            if warn:
                msg = f"Parameter {p} is outside of the suggested range {parameters.pp_range_list[i]}."
                core.logger.warning(msg)

    return parameters


def check_system_parameters(parameters):
    """check if parameter module has correct attributes
    # TODO: check if attributes are of correct type etc. (pydantic)
    Args:
        parameters (module):
    """
    returncode = 0
    if not hasattr(parameters, "model_name"):
        log_msg = "model_name attribute missing in parameters.py"
        returncode = 1
    elif not hasattr(parameters, "pp_symb"):
        log_msg = "pp_symb attribute missing in parameters.py"
        returncode = 2
    elif not hasattr(parameters, "pp_sf"):
        log_msg = "pp_sf attribute missing in parameters.py"
        returncode = 3
    elif not hasattr(parameters, "pp_subs_list"):
        log_msg = "pp_subs_list attribute missing in parameters.py"
        returncode = 4
    elif not hasattr(parameters, "latex_names"):
        log_msg = "latex_names attribute missing in parameters.py"
        returncode = 5
    elif not hasattr(parameters, "tabular_header"):
        log_msg = "tabular_header attribute missing in parameters.py"
        returncode = 6
    elif not hasattr(parameters, "col_alignment"):
        log_msg = "col_alignment attribute missing in parameters.py"
        returncode = 7
    elif not hasattr(parameters, "col_1"):
        log_msg = "col_1 attribute missing in parameters.py"
        returncode = 8
    elif not hasattr(parameters, "start_columns_list"):
        log_msg = "start_columns_list attribute missing in parameters.py"
        returncode = 9
    elif not hasattr(parameters, "end_columns_list"):
        log_msg = "end_columns_list attribute missing in parameters.py"
        returncode = 10

    if returncode != 0:
        core.logger.error(msg=log_msg)

    return returncode


def create_system_model_list_pdf():
    """create a pdf file of all know system models"""
    res = run_command(["pdflatex", "-version"], logger=core.logger, capture_output=False)
    assert res.returncode == 0, "Command 'pdflatex' not recognized. Check installation and availability in PATH."

    # put tex and pdf in root directory
    output_dir = os.path.join(core.root_path, "local_outputs")
    if not os.path.isdir(output_dir):
        os.mkdir(output_dir)
    os.chdir(output_dir)

    tex_file_name = "system_model_list.tex"
    try:
        os.unlink(tex_file_name)
    except FileNotFoundError:
        pass
    tex_file = open(tex_file_name, "a")

    header = []
    body = []
    # iterate all models
    for sm in models.SystemModel.objects.all():
        model_file_path = os.path.join(core.data_path, os.pardir, sm.base_path, "_data", "documentation.tex")
        model_file = open(model_file_path, "r")
        lines = model_file.readlines()
        begin = None
        end = None

        for i, v in enumerate(lines):
            # strip lines of repetetive headers etc.
            if "\\begin{document}" in v:
                begin = i + 1
            if "\\end{document}" in v:
                end = i
            # change captions for uniform look
            if "\\part*{Model Documentation of the:}" in v:
                lines[i] = "\n"
            if "Add Model Name" in v:
                lines[i] = "\\part{" + sm.name + "}\n" + "ACKREP-Key: " + sm.key
            if "\\input{parameters.tex}" in v:
                lines[i] = (
                    "\\input{"
                    + str(
                        os.path.join(core.data_path, os.pardir, sm.base_path, "_data", "parameters.tex").replace(
                            "\\", "/"
                        )
                    )
                    + "}\n"
                )
            if "\\begin{thebibliography}" in v:
                lines[i] = _import_png_to_tex(sm) + lines[i]

        assert isinstance(begin, int) and isinstance(
            end, int
        ), f"documentation.tex of {sm.name} is missing \\begin / \\end of document. "
        new_header = lines[0:begin]
        if len(header) == 0:
            header = new_header
        else:
            for line in new_header:
                if not line in header:
                    header.insert(len(header) - 1, line)

        body = body + lines[begin:end]
        body.append("\n\\newpage\n")
        model_file.close()

    # reset section counter with each model
    header.insert(len(header) - 1, "\\usepackage{chngcntr}\n\\counterwithin*{section}{part}\n")

    tex_file.writelines(header)
    tex_file.write("\n\\title{Model Documentation}\n\\maketitle\n\\newpage\n")
    tex_file.writelines(body)
    tex_file.write("\n\\end{document}")
    tex_file.close()

    res = run_command(["pdflatex", "-halt-on-error", tex_file_name], logger=core.logger, capture_output=True)

    return res


def _import_png_to_tex(system_model_entity):
    assert type(system_model_entity) == models.SystemModel, f"{system_model_entity} is not of type model.SystemModel"
    res = core.check_generic(system_model_entity.key)
    line = "\n\\section{Simulation}\n"

    png_path = os.path.join(core.data_path, os.pardir, system_model_entity.base_path, "_data")
    for file in os.listdir(png_path):
        if ".png" in file:
            path = os.path.join(png_path, file).replace("\\", "/")

            line = (
                line
                + "\\begin{figure}[H]\n"
                + "\\centering\n"
                + "\\includegraphics[width=\\linewidth]{"
                + path
                + "}\n"
                + "\\caption{Simulation of the "
                + system_model_entity.name
                + ".}\n"
                + "\\end{figure}\n"
            )

    return line
