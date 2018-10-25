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

""" Abstract syntax tree (AST) transformers to support tracing.
"""
from __future__ import absolute_import

import ast
from collections import OrderedDict
import sys
try:
    # Python 3.3+
    from inspect import signature
except ImportError:
    # Python 2.7 to 3.2
    from funcsigs import signature

import astor


def make_tracing_call_wrapper(on_call=None, on_return=None):
    """ Higher-order function to create call wrappers for tracing.

    The wrapper calls the given functions before and/or after the wrapped
    function is called.
    """
    def wrapper(fun, *args, **kwargs):
        # Pre-call.
        arguments = bind_arguments(fun, *args, **kwargs)
        if on_call is not None:
            on_call(fun, arguments)

        # Call!
        return_value = fun(*args, **kwargs)

        # Post-call.
        if on_return is not None:
            on_return(fun, arguments, return_value)

        return return_value
    
    return wrapper


def bind_arguments(fun, *args, **kwargs):
    """ Bind arguments to function or method.

    Returns an ordered dictionary mapping argument names to values.
    """
    try:
        sig = signature(fun)
    except ValueError:
        # Sigantures doesn't exist for certain builtin functions.
        # https://stackoverflow.com/q/42134927
        arguments = OrderedDict()
        for i, value in enumerate(args):
            arguments['__arg%i__' % i] = value # Make up argument names.
        for key, value in kwargs.items():
            arguments[key] = value
        return arguments
    
    # If we have a signature, use it to bind the arguments.
    bound = sig.bind(*args, **kwargs)
    return bound.arguments


class WrapCalls(astor.TreeWalk):
    """ Wrap all function and method calls in AST.

    Replaces function and method calls, e.g.

        f(x,y,z=1)
    
    with wrapped calls, e.g.

        wrapper(f, x, y, z=1)
    """

    def __init__(self, wrapper, node=None):
        astor.TreeWalk.__init__(self, node=node)
        self.wrapper = wrapper
    
    def post_Call(self):
        call = self.cur_node
        new_args = [ call.func ] + call.args
        if sys.version_info.major >= 3 and sys.version_info.minor >= 5:
            # Representation of *args and **kwargs changed in Python 3.5.
            new_call = ast.Call(self.wrapper, new_args, call.keywords)
        else:
            new_call = ast.Call(self.wrapper, new_args, call.keywords,
                                call.starargs, call.kwargs)
        self.replace(new_call)
