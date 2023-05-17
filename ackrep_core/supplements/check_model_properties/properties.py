import symbtools as st
import sympy as sp
import functools
from ipydex import IPS

from threading import Thread
from ackrep_core.system_model_management import GenericModel

class TimeoutException(Exception):
    pass

# source of decorator for the timeout:
# https://stackoverflow.com/questions/21827874/timeout-a-function-windows

def timeout(timeout):
    def deco(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            res = [TimeoutException('function [%s] timeout [%s seconds] exceeded!' % (func.__name__, timeout))]
            def newFunc():
                try:
                    res[0] = func(*args, **kwargs)
                except Exception as e:
                    res[0] = e
            t = Thread(target=newFunc)
            t.daemon = True
            try:
                t.start()
                t.join(timeout)
            except Exception as je:
                print ('error starting thread')
                raise je
            ret = res[0]
            if isinstance(ret, BaseException):
                raise ret
            return ret
        return wrapper
    return deco

def locally_strongly_accessible(model: GenericModel):
    """
    checks if model is locally strongly accessible

    :reutrn: tuple of flag - boolean, msg - string
    """
    if not isinstance(model, GenericModel):                     # models with not useable representation
        flag = None
        msg = "model representation not useable"
    elif not model.uu_symb:                                     # models without input
        flag = None
        msg = "model has no input"
    else:
        eqns: st.MatrixBase = model.get_rhs_symbolic()
        if not eqns:                                            # models without function get_rhs_symbolic()
            flag = None
            msg = "model representation not useable"
        else:
            xx = model.xx_symb
            uu = model.uu_symb

            ff = eqns.subz0(uu)
            gg: st.MatrixBase = eqns - ff

            GG = gg.jacobian(uu)
            d = (GG - GG.subz0(uu)).srn                         # d != 0 where gg depends nonlinearly on u

            if any(d):                                          # check if model is linearly dependent on u
                flag = None
                msg = "not input affine"
            else:
                flag, msg = calculate_access(ff, gg, xx, model)

    return (flag, msg)

@timeout(600)
def calculate_access(ff, gg, xx, model):
    """
    determines if the model is locally strongly accessible or not

    :return: list of flag - boolean, msg - string
    """
    ff = ff.subs(model.pp_subs_list)
    gg = gg.subs(model.pp_subs_list)

    n = len(xx)

    lb_f1g = st.lie_bracket(ff, gg, xx)
    D = st.col_stack(gg, lb_f1g)

    for i in range(n):
        if st.generic_rank(D) == n:
            flag = True
            msg = "local strong access"
            break
        else:
            flag = False
            msg = "no local strong access"

        lb_fg = st.lie_bracket(ff, D[:, -1], xx)
        D = st.col_stack(D, lb_fg)

    return [flag, msg]

@timeout(600)
def exact_input_state_linearization(model: GenericModel):
    """
    Check if the model of the form $\dot{x}=f(x) + g(x)u$ has an exact input state lineraization in $p$. The criterion
    presented in [1, chap. 4.2] uses the distribution $\Delta_i(x) = \span\{g(x), ad_{-f}g(x),...,ad_{-f}^{i-1}g(x)\}$
    to evaluate two conditions:
    1. $ \text{dim}\Delta(p)$
    2. $ \Delta_{n-1}$ ist involutiv in einer Umgebung von p.

    [1] K. Röbenack, Nichtlineare Regelungssysteme: Theorie und Anwendung der exakten Linearisierung.
    Berlin, Heidelberg: Springer Berlin Heidelberg, 2017. doi: 10.1007/978-3-662-44091-9.
    """
    if not isinstance(model, GenericModel):                     # models with not useable representation
        flag = None
        msg = "model representation not useable"
    elif not model.uu_symb:                                     # models without input
        flag = None
        msg = "model has no input"
    else:
        eqns: st.MatrixBase = model.get_rhs_symbolic()
        if not eqns:                                            # models without function get_rhs_symbolic()
            flag = None
            msg = "model representation not useable"
        else:
            xx = model.xx_symb
            uu = model.uu_symb

            ff = eqns.subz0(uu)
            gg: st.MatrixBase = sp.simplify(eqns - ff)

            GG = gg.jacobian(uu)
            d = (GG - GG.subz0(uu)).srn                         # d != 0 where gg depends nonlinearly on u

            if any(d):                                          # check if model is linearly dependent on u
                flag = None
                msg = "not input affine"
            else:                                               # actually calculate linearization
                ff = ff.subs(model.pp_subs_list)
                gg = gg.subs(model.pp_subs_list)

                n = model.n

                # build distribution
                delta_n_list = [gg]
                for i in range(1,n):
                    delta_n_list.append(st.lie_bracket(-ff, gg, xx, order=i))
                delta_n = sp.Matrix([delta_n_list])

                cond1 = False
                cond2 = False

                # condition 1, dim(delta_n) == n
                cond1 = st.generic_rank(delta_n) == n

                # condition 2, delta_n-1 involutiv
                delta_n1 = sp.Matrix([delta_n_list[:-1]])
                cond2, _ = st.involutivity_test(delta_n1, xx)

                flag = cond1 and cond2
                msg = f"exact input state linearization {'exists' if flag else 'does not exist'}"

    return flag, msg