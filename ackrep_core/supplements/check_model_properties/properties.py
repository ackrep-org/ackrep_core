import symbtools as st
import numpy as np
import sympy as sp
from ipydex import IPS
from abc import abstractmethod
import copy


from ackrep_core.system_model_management import GenericModel

from util import timeout


class TimeoutException(Exception):
    pass


class Property:
    erk_key = None

    @abstractmethod
    def check_property(self):
        raise NotImplementedError


class LocalStrongAccess(Property):
    erk_key = "I7178"

    def check_property(self, model: GenericModel):
        """
        checks if model is locally strongly accessible

        :reutrn: tuple of flag - boolean, msg - string
        """
        if not isinstance(model, GenericModel):  # models with not useable representation
            flag = None
            msg = "model representation not useable"
        elif not model.uu_symb:  # models without input
            flag = None
            msg = "model has no input"
        else:
            eqns: st.MatrixBase = model.get_rhs_symbolic()
            if not eqns:  # models without function get_rhs_symbolic()
                flag = None
                msg = "model representation not useable"
            else:
                xx = model.xx_symb
                uu = model.uu_symb

                ff = eqns.subz0(uu)
                gg: st.MatrixBase = eqns - ff

                GG = gg.jacobian(uu)
                d = (GG - GG.subz0(uu)).srn  # d != 0 where gg depends nonlinearly on u

                if any(d):  # check if model is linearly dependent on u
                    flag = None
                    msg = "not input affine"
                else:
                    flag, msg = self.calculate_access(ff, gg, xx, model)

        return (flag, msg)

    @timeout(600)
    def calculate_access(self, ff, gg, xx, model):
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


class ExactInputStateLinearization(Property):
    erk_key = "I5358"

    @timeout(600)
    def check_property(self, model: GenericModel):
        """
        SISO:
        Check if the model of the form $\dot{x}=f(x) + g(x)u$ has an exact input state lineraization in $p$. The criterion
        presented in [1, chap. 4.2] uses the distribution $\Delta_i(x) = \span\{g(x), ad_{-f}g(x),...,ad_{-f}^{i-1}g(x)\}$
        to evaluate two conditions:
        1. $ \text{dim}\Delta(p)$
        2. $ \Delta_{n-1}$ ist involutiv in einer Umgebung von p.

        MIMO:
        vector relative degree [2, chap. 5.2]


        [1] K. Röbenack, Nichtlineare Regelungssysteme: Theorie und Anwendung der exakten Linearisierung.
        Berlin, Heidelberg: Springer Berlin Heidelberg, 2017. doi: 10.1007/978-3-662-44091-9.
        [2] A. Isidori, Nonlinear Control Systems. Berlin, Heidelberg: Springer Berlin Heidelberg, 1989. doi: 10.1007/978-3-662-02581-9.
        """
        if not isinstance(model, GenericModel):  # models without useable representation
            flag = None
            msg = "model representation not useable"
        elif not model.uu_symb:  # models without input
            flag = None
            msg = "model has no input"
        # MIMO case
        elif len(model.uu_symb) > 1:
            eqns: st.MatrixBase = model.get_rhs_symbolic()
            if not eqns:  # models without function get_rhs_symbolic()
                flag = None
                msg = "model representation not useable"
            else:
                xx = model.xx_symb
                uu = model.uu_symb

                ff = eqns.subz0(uu)
                gg: st.MatrixBase = sp.simplify(eqns - ff)

                GG = gg.jacobian(uu)
                d = (GG - GG.subz0(uu)).srn  # d != 0 where gg depends nonlinearly on u

                if any(d):  # check if model is linearly dependent on u
                    flag = None
                    msg = "not input affine"
                else:  # actually calculate linearization

                    ff = ff.subs(model.pp_subs_list)
                    GG = GG.subs(model.pp_subs_list)

                    n = model.n
                    m = len(model.uu_symb)

                    if st.generic_rank(GG) != m:
                        flag = None
                        msg = "g not of full rank"
                        return flag, msg

                    # LAMBDA = np.zeros((m,m), dtype=object)
                    # h = xx
                    # for r in LAMBDA:
                    #     for c in r:
                    #         k = 0
                    #         Lfh = st.lie_deriv(h[r], ff, xx, order=k)
                    #         LgLfh = st.lie_deriv(Lfh, GG[:,c], xx)
                    #         while LgLfh == 0:
                    #             k += 1
                    #             Lfh = st.lie_deriv(h[r], ff, xx, order=k)
                    #             LgLfh = st.lie_deriv(Lfh, GG[:,c], xx)

                    #         LAMBDA[r,c] = LgLfh

                    # build distribution
                    # Gi = span{ad_f^k g_j : 0 <= k <= i, 1 <= j <= m}
                    G_list = []
                    for i in range(n):
                        if len(G_list) > 0:
                            Gi = copy.copy(G_list[-1])
                        else:
                            Gi = []
                        for j in range(m):
                            Gi.append(st.lie_bracket(ff, GG[:, j], xx, order=i))
                        G_list.append(Gi)

                    cond1 = True
                    seed1 = 1
                    seed2 = 2
                    print("checking cond. 1 ...")
                    for i in range(n):
                        dim1 = st.generic_rank(sp.Matrix([G_list[i]]), seed=seed1)
                        dim2 = st.generic_rank(sp.Matrix([G_list[i]]), seed=seed2)

                        cond1 = dim1 == dim2
                        if not cond1:
                            print("cond 1 failed")
                            break

                    if cond1:

                        print("checking cond. 2...")
                        cond2 = st.generic_rank(sp.Matrix([G_list[-1]])) == n
                        if cond2:
                            print("cond. 2 ok")
                            cond3 = True
                            for i in range(n - 1):
                                cond3 = st.involutivity_test(sp.Matrix([G_list[i]]), xx)[0]
                                if cond3 == False:
                                    print(f"cond3 failed at i={i}")
                                    # IPS()
                                    break
                        else:
                            print("cond2 failed")
                            cond3 = False
                    else:
                        cond2 = cond3 = False

                    flag = cond1 and cond2 and cond3
                    msg = f"exact input state linearization {'exists' if flag else 'does not exist'}"
        # SISO case
        else:
            eqns: st.MatrixBase = model.get_rhs_symbolic()
            if not eqns:  # models without function get_rhs_symbolic()
                flag = None
                msg = "model representation not useable"
            else:
                xx = model.xx_symb
                uu = model.uu_symb

                ff = eqns.subz0(uu)
                gg: st.MatrixBase = sp.simplify(eqns - ff)

                GG = gg.jacobian(uu)
                d = (GG - GG.subz0(uu)).srn  # d != 0 where gg depends nonlinearly on u

                if any(d):  # check if model is linearly dependent on u
                    flag = None
                    msg = "not input affine"
                else:  # actually calculate linearization
                    ff = ff.subs(model.pp_subs_list)
                    gg = gg.subs(model.pp_subs_list)

                    n = model.n

                    # build distribution
                    delta_n_list = [gg]
                    for i in range(1, n):
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
