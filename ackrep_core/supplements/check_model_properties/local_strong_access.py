import symbtools as st
import functools

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
            d = (GG - GG.subz0(uu)).srn 

            if any(d):                                          # check if model is linearly dependent on u
                flag = None
                msg = "not linearly dependent on u"
            else:
                try:
                    flag, msg = calculate_access(ff, gg, xx, model)
                except TimeoutException:
                    flag, msg = [None, "timeout"]
                except ValueError as e:
                    flag, msg = [None, str(e)]

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