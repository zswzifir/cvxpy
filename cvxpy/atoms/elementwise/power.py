"""
Copyright 2013 Steven Diamond

This file is part of CVXPY.

CVXPY is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

CVXPY is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with CVXPY.  If not, see <http://www.gnu.org/licenses/>.
"""

import cvxpy.utilities as u
import cvxpy.lin_ops.lin_utils as lu
from .elementwise import Elementwise
import numpy as np
from fractions import Fraction
from ...utilities.power_tools import sanitize_scalar, is_power2, gm_constrs


class power(Elementwise):
    r""" Elementwise power function :math:`f(x) = x^p`.

    .. math::

        \begin{array}{ccl}
        p = 0 & f(x) = 1 & \text{constant, positive} \\
        p = 1 & f(x) = x & \text{affine, increasing, same sign as $x$} \\
        p = 2,4,8,\ldots &f(x) = |x|^p  & \text{convex, signed monotonicity, positive} \\
        p < 0 & f(x) = \begin{cases} x^p & x > 0 \\ +\infty & x \leq 0 \end{cases} & \text{convex, decreasing, positive} \\
        0 < p < 1 & f(x) = \begin{cases} x^p & x \geq 0 \\ -\infty & x < 0 \end{cases} & \text{concave, increasing, positive} \\
        p > 1,\ p \neq 2,4,8,\ldots & f(x) = \begin{cases} x^p & x \geq 0 \\ +\infty & x < 0 \end{cases} & \text{convex, increasing, positive}
        \end{array}

    .. note::

        To get the increasing branch, compose with.
        To get the symmetric branch, compose with
        The final monotonicity and curvature depend on the rational approximation of p


    Parameters
    ----------

    x : cvx.Variable

    p : int, float, or Fraction
        Scalar power.



    """
    def __init__(self, x, p):

        # need to convert p right away to a fraction or integer
        p = sanitize_scalar(p)

        if p > 1:
            p, w = pow_high(p)
        elif 0 < p < 1:
            p, w = pow_mid(p)
        elif p < 0:
            p, w = pow_neg(p)

        # note: if, after making the rational approximation, p ends up being 0 or 1,
        # we default to using the 0 or 1 behavior of the atom, which affects the curvature, domain, etc...
        # maybe unexpected behavior to the user if they put in 1.00001?

        if p == 1:
            # in case p is a fraction equivalent to 1
            p = 1
            w = None
        if p == 0:
            p = 0
            w = None

        self.p, self.w = p, w

        super(power, self).__init__(x)

    @Elementwise.numpy_numeric
    def numeric(self, values):
        if self.p == 0:
            return np.ones(self.size)
        else:
            return np.power(values[0], self.p)

    def sign_from_args(self):
        if self.p == 1:
            # same sign as input
            return self.args[0]._dcp_attr.sign
        else:
            return u.Sign.POSITIVE

    def func_curvature(self):
        if self.p == 0:
            return u.Curvature.CONSTANT
        elif self.p == 1:
            return u.Curvature.AFFINE
        elif self.p < 0 or self.p > 1:
            return u.Curvature.CONVEX
        elif 0 < self.p < 1:
            return u.Curvature.CONCAVE

    def monotonicity(self):
        if self.p == 0:
            # todo: is this right? what do do for constant monotonicity
            return [u.monotonicity.NONMONOTONIC]
        if self.p == 1:
            return [u.monotonicity.INCREASING]
        if self.p < 0:
            return [u.monotonicity.DECREASING]
        if 0 < self.p < 1:
            return [u.monotonicity.INCREASING]
        if self.p > 1:
            if is_power2(self.p):
                return [u.monotonicity.SIGNED]
            else:
                return [u.monotonicity.INCREASING]

    def validate_arguments(self):
        pass

    def get_data(self):
        return self.p, self.w

    @staticmethod
    def graph_implementation(arg_objs, size, data=None):
        """Reduces the atom to an affine expression and list of constraints.

        Parameters
        ----------
        arg_objs : list
            LinExpr for each argument.
        size : tuple
            The size of the resulting expression.
        data :
            Additional data required by the atom.

        Returns
        -------
        tuple
            (LinOp for objective, list of constraints)
        """
        x = arg_objs[0]
        p, w = data

        if p == 1:
            return x, []
        else:
            one = lu.create_const(np.mat(np.ones(size)), size)
            if p == 0:
                return one, []
            else:
                t = lu.create_var(size)

                if 0 < p < 1:
                    return t, gm_constrs(t, [x, one], w)
                elif p > 1:
                    return t, gm_constrs(x, [t, one], w)
                elif p < 0:
                    return t, gm_constrs(one, [x, t], w)
                else:
                    raise NotImplementedError('this power is not yet supported.')

    def name(self):
        return "%s(%s, %s)" % (self.__class__.__name__,
                                 self.args[0].name(),
                                 self.p)


def pow_high(p, max_denom=1024):
    """ Return (t,1,x) power tuple

        x <= t^(1/p) 1^(1-1/p)

        user wants the epigraph variable t
    """
    assert p > 1
    p = Fraction(1/Fraction(p)).limit_denominator(max_denom)
    if 1/p == int(1/p):
        return int(1/p), (p, 1-p)
    return 1/p, (p, 1-p)


def pow_mid(p, max_denom=1024):
    """ Return (x,1,t) power tuple

        t <= x^p 1^(1-p)

        user wants the epigraph variable t
    """
    assert 0 < p < 1
    p = Fraction(p).limit_denominator(max_denom)
    return p, (p, 1-p)


def pow_neg(p, max_denom=1024):
    """ Return (x,t,1) power tuple

        1 <= x^(p/(p-1)) t^(-1/(p-1))

        user wants the epigraph variable t
    """
    assert p < 0
    p = Fraction(p)
    p = Fraction(p/(p-1)).limit_denominator(max_denom)
    return p/(p-1), (p, 1-p)