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
import sys
from .ast_transform import to_attribute, to_call, to_name

from traitlets import HasTraits, Any

# Does `ast.Starred` exist?
ast_has_starred = sys.version_info.major >= 3 and sys.version_info.minor >= 5


class ASTTracer(HasTraits):
    """ Trace function and method calls by AST rewriting.

    This class should be used with the `TraceFunctionCalls` AST transformer. 
    It is very low-level and should be supplemented with additional logic to be
    useful. The `Tracer` class in this subpackage shows how to do this in an
    event-based way.
    """

    def trace_function(self, function, nargs):
        """ Called after function object (not function call!) is evaluated.
        """
        return self._unbox(self._trace_function(function, nargs))
    
    def trace_argument(self, arg_value, arg_name=None, nstars=0):
        """ Called after function argument is evaluated.
        """
        return self._unbox(self._trace_argument(arg_value, arg_name, nstars))

    def trace_return(self, return_value):
        """ Called after function returns.
        """
        return self._unbox(self._trace_return(return_value))
    
    def _trace_function(self, function, args):
        """ Called after function object is evaluated.
        
        May be reimplemented in subclass.
        """
        return function
    
    def _trace_argument(self, arg_value, arg_name=None, nstars=0):
        """ Called after function argument is evaluated.
        
        May be reimplemented in subclass.
        """
        return arg_value
    
    def _trace_return(self, return_value):
        """ Called after function returns.

        May be reimplemented in subclasss.
        """
        return return_value
    
    def _unbox(self, x):
        """ Unbox a value, if it is boxed.
        """
        return x.value if isinstance(x, BoxedValue) else x


class TraceFunctionCalls(ast.NodeTransformer):
    """ Rewrite AST to trace function and method calls.

    Replaces function and method calls, e.g.

        f(x,y,z=1)
    
    with wrapped calls, e.g.

        trace_return(trace_function(f)(
            trace_argument(x), trace_argument(y), z=trace_argument(1,'z')))
    """

    def __init__(self, tracer):
        super(TraceFunctionCalls, self).__init__()
        self.tracer = to_name(tracer)
    
    def trace_method(self, method):
        return to_attribute(self.tracer, method)
    
    def trace_function(self, func, nargs):
        return to_call(self.trace_method('trace_function'), [
            func, ast.Num(nargs)
        ])
    
    def trace_argument(self, arg_value, arg_name=None, nstars=0):
        # Unpack starred expression in Python 3.5+.
        starred = ast_has_starred and isinstance(arg_value, ast.Starred)
        if starred:
            arg_value = arg_value.value
            nstars = 1
        
        # Create new call.
        args = [ arg_value ]
        if arg_name:
            args += [ ast.Str(arg_name) ]
        keywords = []
        if nstars:
            keywords += [ ast.keyword('nstars', ast.Num(nstars)) ]
        call = to_call(self.trace_method('trace_argument'), args, keywords)

        # Repack starred expression in Python 3.5+.
        if starred:
            call = ast.Starred(call, ast.Load())
        return call
    
    def trace_return(self, return_value):
        return to_call(self.trace_method('trace_return'), [return_value])
    
    def visit_Call(self, call):
        """ Rewrite AST Call node.
        """
        self.generic_visit(call)
        args = [ self.trace_argument(arg) for arg in call.args ]
        keywords = [ ast.keyword(kw.arg, self.trace_argument(
                        kw.value, kw.arg, 2 if kw.arg is None else 0
                     )) for kw in call.keywords ]
        nargs = len(args) + len(keywords)

        # Handle *args and **kwargs in Python 3.4 and lower.
        starargs, kwargs = None, None
        if not ast_has_starred:
            if call.starargs is not None:
                starargs = self.trace_argument(call.starargs, nstars=1)
                nargs += 1
            if call.kwargs is not None:
                kwargs = self.trace_argument(call.kwargs, nstars=2)
                nargs += 1

        return self.trace_return(
            to_call(self.trace_function(call.func, nargs),
                    args, keywords, starargs, kwargs)
        )


class BoxedValue(HasTraits):
    """ A boxed value.

    Boxed values can be to pass extra data, not contained in the original
    program, between tracer callbacks. This is useful for connecting function
    arguments to the function call, for example.

    Note that the value in the box may have any type, not necessarily primitive.
    """
    value = Any()