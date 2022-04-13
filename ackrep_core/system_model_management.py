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

from . import core
from .util import root_path



class GenericModel:
    t_symb = sp.Symbol('t')
        
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
            
        Notes:
        =====         
        The dimension of an existing model-object can't be changed.
        The parameters and input function of an existing model-object 
        can be changed.

        """
        # Initialize all Parameters of the Model-Object with None 
        # Indicator for the existance of parameters
        self.has_params = None
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
        # Parameter Substitution List for sp.subs methods
        self.pp_subs_list = None
        # Input function
        self.uu_func = None
        

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
    
    @abc.abstractmethod    
    def uu_default_func(self):
        """
        Creates a default input function for the given model.
        The default input function has following purposes:
            - model validation during implementation
            - make generated model simulatable without additional effort to
              create a new, nontrivial input
            - give an example for the system response
                
        :return:(function f) default input function
        
            The returned function shall take two parameters :
                t : scalar or list 
                    scalar: time at which the input function shall be 
                            evaluated        
                    list: times at which the input function shall be evaluated
                    
                xx_nv : list or list of lists 
                    list: state vector of the model at time t
                    list of lists: state vectors of the model at the times in t
                    
            The returned function shall return :
                list: values of input vector uu at time t
                list of lists: values of input vectors at the times in t                
        """ 
     
        
    # ----------- SET STATE VECTOR DIMENSION ---------- # 
    
    def _set_dimension(self, x_dim):
        """
        :param dim:(int > 0), Order of the system
        """
        # check if system is n-extendable
        if self.n is not None:
            warnings.warn("Function \"set_dimension\" had no effect. \
                          System is not n-extendable.")            
            return
        # check if :param dim: is valid -- ADJUSTION NEEDED IN SPECIAL CASES
        assert(x_dim > 0 and isinstance(x_dim, int)), \
                "Param: x_dim isn't valid."
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
            # Check if parameter values are valid 
            self._validate_p_values(p_values)          
            # Take Keys in the dict as parameter symbols
            self.pp_symb = list(pp.keys())
            assert isinstance(self.pp_symb, sp.Symbol), \
                                "param pp: keys aren't of type sp.Symbol"
            self.pp_dict = pp
        else:  # --> pp is a list type object
            assert pp_symb is not None, "pp_symb is expected not to be None, \
                                    because pp is not a dict type object"
            # Check if parameters are valid     
            self._validate_p_values(pp)
            # Define symbolic parameter vector
            self.pp_symb = pp_symb
            # create parameter dict
            parameter_number = len(pp_symb)
            self.pp_dict = {self.pp_symb[i]:pp[i] for i 
                            in range(parameter_number)}


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


    # ----------- VALIDATE PARAMETER VALUES ---------- #
    
    @abc.abstractmethod
    def validate_p_values(self, p_value_list):
        """Checks if the given parameter values are valid and 
        throws exception if values aren't valid. 
        
        :param p_value_list:(list) parameter values
        """
        
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
        # transform symbolic function to numerical function
        dxx_dt_func = sp.Matrix(self.get_rhs_symbolic())
        # Substitute Parameters with numerical Values
        self._create_subs_list()
        dxx_dt_func = dxx_dt_func.subs(self.pp_subs_list)
        # Create executable rhs function
        dxx_dt_func = sp.lambdify(self._xxuu_symb, list(dxx_dt_func), 
                                    modules = 'numpy')        
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
        self.uu_symb = [sp.Symbol('u' + str(i)) for i in range(0, self.u_dim)]

    
    # ----------- CREATE SYMBOLIC STATE AND COMBINED VECTOR ---------- #
    
    def _create_symb_xx_xxuu(self):
        # create new symbolic state vector
        self.xx_symb = [sp.Symbol('x' + str(i)) for i in range(0, self.n)]
        self._xxuu_symb = self.xx_symb + self.uu_symb   
        
        
    # ----------- CREATE SYMBOLIC PARAMETER VECTOR ---------- #
    
    def _create_symb_pp(self, symb_pp_list=None):
        if symb_pp_list is not None:
            assert isinstance(symb_pp_list, list), \
                        ":param symb_pp_list: is not a list type object"
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
    p_symbols = [sp.latex(pp_dict_key_list[i], symbol_names=parameters.latex_names) 
                 for i in range(len(parameters.get_default_parameters()))]
    # set cells in math-mode
    for i in range(len(p_symbols)):
        p_symbols[i] = "$" + p_symbols[i] + "$"
    
    # Define "Value" column
    p_values = [sp.latex(p_sf) for p_sf in parameters.pp_sf]
    # set cells in math-mode
    for i in range(len(p_values)):
        p_values[i] = "$" + p_values[i] + "$"
    
    # Create list, which contains the content of the table body
    table_body_list = np.array([*parameters.start_columns_list, p_symbols, p_values, 
                                *parameters.end_columns_list])
    # Convert list of column entries to list of row entries
    table = table_body_list.transpose()
    
    # Create string which contains the latex-code of the tabular
    tex = tab.tabulate(table, parameters.tabular_header, tablefmt = 'latex_raw', 
                       colalign = parameters.col_alignment)
    
    # Change Directory to the Folder of the Model. 
    cwd = os.path.dirname(os.path.abspath(__file__))
    parent2_cwd = os.path.dirname(os.path.dirname(cwd))
    path_base = os.path.join(root_path, parameters.base_path, "_system_model_data") 
    os.chdir(path_base)
    # Write tabular to Parameter File.
    file = open("parameters.tex", 'w')
    file.write(tex)
    file.close()
    
    # delete aux files created by latex
    # TODO: better solution fpr sleep, right now this is done since aux files take some time to be generated
    import time
    time.sleep(3)
    all_files = core.get_system_model_data_files(parameters.base_path)
    allowed_list = [".tex", ".png", ".pdf"]

    for file in all_files:
        if file[-4:] not in allowed_list:
            os.remove(os.path.split(file)[1])


def import_parameters(key):
    """import parameters.py selected be given key and create related get function for system_model

    Args:
        key: key of system_model

    Returns:
        module: parameters
    """
    sys.path.insert(0, root_path)
    
    system_model_entity = core.model_utils.get_entity(key)
    base_path = system_model_entity.base_path
    mod_path = os.path.join(base_path, "parameters")
    if not os.path.isfile(os.path.join(root_path, base_path, "parameters.py")):
        raise FileNotFoundError(f"Import of parameters.py failed. Path {base_path} does not lead to parameters.py.")
    mod_path = ".".join(mod_path.split(os.path.sep))

    parameters = importlib.import_module(mod_path)
    parameters.base_path = base_path

    assert hasattr(parameters, "pp_symb")
    assert hasattr(parameters, "pp_sf")
    pp_nv = list(sp.Matrix(parameters.pp_sf).subs(parameters.pp_subs_list))
    pp_dict = {parameters.pp_symb[i]:pp_nv[i] for i in range(len(parameters.pp_symb))}

    def get_default_parameters():
        return pp_dict
    def get_symbolic_parameters():
        return parameters.pp_symb
    parameters.get_default_parameters = get_default_parameters
    parameters.get_symbolic_parameters = get_symbolic_parameters

    return parameters
