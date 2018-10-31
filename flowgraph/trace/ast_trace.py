# Copyright 2018 IBM Corp.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

""" Abstract syntax tree (AST) transformer to trace function calls.
"""
from __future__ import absolute_import

import ast
from collections import OrderedDict
import inspect
import sys
import types
try:
    # Python 3.3+
    from inspect import signature
except ImportError:
    # Python 2.7 to 3.2
    from funcsigs import signature

from .ast_transform import to_attribute, to_call, to_name


def bind_arguments(fun, *args, **kwargs):
    """ Bind arguments to function or method.

    Returns an ordered dictionary mapping argument names to values. Unlike
    `inspect.signature`, the `self` parameter of bound instance methods is
    included as an argument.
    """
    if inspect.ismethod(fun) and not inspect.isclass(fun.__self__):
        # Case 1: Bound instance method, implemented in Python.
        # Reduce to Case 2 below because `Signature.bind()`` excludes `self`
        # argument in bound methods.
        args = (fun.__self__,) + args
        fun = fun.__func__
    
    try:
        # Case 2: Callable implemented in Python.
        sig = signature(fun)
    except ValueError:
        # `inspect.signature()` doesn't work on builtins.
        # https://stackoverflow.com/q/42134927
        pass
    else:
        # Case 2, cont.: If we got a signature, use it and exit.
        bound = sig.bind(*args, **kwargs)
        return bound.arguments
    
    fun_self = getattr(fun, '__self__', None)
    if fun_self is not None and not isinstance(fun_self, types.ModuleType):
        # Case 3: Method implemented in C ("builtin method").
        # Reduce to Case 4 below.
        args = (fun_self,) + args

    # Case 4: Callable implemented in C ("builtin")
    arguments = OrderedDict()
    for i, value in enumerate(args):
        arguments[str(i)] = value
    for key, value in kwargs.items():
        arguments[key] = value
    return arguments


class TraceFunctionCalls(ast.NodeTransformer):
    """ Rewrite AST to trace function and method calls.

    Replaces function and method calls, e.g.

        f(x,y,z=1)
    
    with wrapped calls, e.g.

        trace_return(trace_function(f)(
            trace_argument(x), trace_argument(y), z=trace_argument(1)))
    """

    def __init__(self, tracer):
        super(TraceFunctionCalls, self).__init__()
        self.tracer = to_name(tracer)
    
    def trace_method(self, method):
        return to_attribute(self.tracer, method)
    
    def trace_function(self, f):
        return to_call(self.trace_method('trace_function'), [f])
    
    def trace_argument(self, arg, kw=None):
        return to_call(self.trace_method('trace_argument'),
                       [arg, ast.Str(kw)] if kw is not None else [arg])
    
    def trace_return(self, return_value):
        return to_call(self.trace_method('trace_return'), [return_value])
    
    def visit_Call(self, call):
        self.generic_visit(call)
        # FIXME: starargs, starkwargs
        # FIXME: Python 2
        args = [ self.trace_argument(arg) for arg in call.args ]
        keywords = [ ast.keyword(kw.arg, self.trace_argument(kw.value, kw.arg))
                     for kw in call.keywords ]
        return self.trace_return(
            to_call(self.trace_function(call.func), args, keywords)
        )

