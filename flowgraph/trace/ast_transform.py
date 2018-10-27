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
import six
import sys
try:
    # Python 3.3+
    from inspect import signature
except ImportError:
    # Python 2.7 to 3.2
    from funcsigs import signature


def make_tracing_call_wrapper(on_call=None, on_return=None, filter_call=None):
    """ Higher-order function to create call wrappers for tracing.

    The wrapper calls the given functions before and/or after the wrapped
    function is called.
    """
    def wrapper(fun, *args, **kwargs):
        # Pre-call.
        arguments = bind_arguments(fun, *args, **kwargs)
        ok = filter_call is None or filter_call(fun, arguments)
        if ok and on_call is not None:
            on_call(fun, arguments)

        # Call!
        return_value = fun(*args, **kwargs)

        # Post-call.
        if ok and on_return is not None:
            on_return(fun, arguments, return_value)

        return return_value
    
    return wrapper


class WrapCalls(ast.NodeTransformer):
    """ Wrap all function and method calls in AST.

    Replaces function and method calls, e.g.

        f(x,y,z=1)
    
    with wrapped calls, e.g.

        wrapper(f, x, y, z=1)
    """

    def __init__(self, wrapper):
        super(WrapCalls, self).__init__()
        self.wrapper = to_name(wrapper)
    
    def visit_Call(self, call):
        self.generic_visit(call)
        new_args = [ call.func ] + call.args
        if sys.version_info.major >= 3 and sys.version_info.minor >= 5:
            # Representation of *args and **kwargs changed in Python 3.5.
            new_call = ast.Call(self.wrapper, new_args, call.keywords)
        else:
            new_call = ast.Call(self.wrapper, new_args, call.keywords,
                                call.starargs, call.kwargs)
        return new_call


class AttributesToFunctions(ast.NodeTransformer):
    """ Replace attribute getters/setters with function calls.

    Namely, the functions `getattr`, `setattr`, and `delattr`.
    """
    
    def visit_Attribute(self, node):
        """ Convert attribute access to `getattr` call.
        """
        self.generic_visit(node)
        if isinstance(node.ctx, ast.Load):
            args = [ node.value, ast.Str(node.attr) ]
            return to_call(to_name('getattr'), args)
        return node
    
    def visit_Assign(self, node):
        """ Convert assignment to attributes to `setattr` call.
        """
        self.generic_visit(node)
        if len(node.targets) > 1:
            # Multiple assignment not implemented.
            return node
        
        target = node.targets[0]
        if isinstance(target, ast.Name):
            return node
        elif isinstance(target, ast.Attribute):
            args = [ target.value, ast.Str(target.attr), node.value ]
            return ast.Expr(to_call(to_name('setattr'), args))

        # Destructuring assignment not implemented.
        return node
        
    def visit_Delete(self, node):
        """ Convert `del` on attributes to `delattr` call.
        """
        self.generic_visit(node)
        stmts = []
        for target in node.targets:
            if isinstance(target, ast.Attribute):
                args = [ target.value, ast.Str(target.attr) ]
                stmts.append(ast.Expr(to_call(to_name('delattr'), args)))
            else:
                stmts.append(ast.Delete([target]))
        return stmts


class OperatorsToFunctions(ast.NodeTransformer):
    """ Replace unary, binary, and other operators with function calls.
    """

    def __init__(self, operator_module=None):
        super(OperatorsToFunctions, self).__init__()
        self.operator = to_name(operator_module or 'operator')


# Helper functions

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
            arguments[str(i)] = value
        for key, value in kwargs.items():
            arguments[key] = value
        return arguments
    
    # If we have a signature, use it to bind the arguments.
    bound = sig.bind(*args, **kwargs)
    return bound.arguments

def to_call(func, args=[], keywords=[], **kwargs):
    """ Create Call AST node.
    """
    return ast.Call(func=func, args=args, keywords=[], **kwargs)

def to_name(str_or_name, ctx=None):
    """ Cast a string to a Name AST node. 
    """
    ctx = ctx or ast.Load()
    if isinstance(str_or_name, six.string_types):
        id = str_or_name
    elif isinstance(str_or_name, ast.Name):
        id = str_or_name.id
    else:
        raise TypeError("Argument must be a string or a Name AST node")
    return ast.Name(id, ctx)
