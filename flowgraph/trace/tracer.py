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

from __future__ import absolute_import

import ast
from collections import deque, OrderedDict
import six
import types

from traitlets import HasTraits, Any, Bool, Instance, Int, List

from .ast_tracer import ASTTracer, ASTTraceTransformer
from .ast_transform import EliminateMultipleTargets, AttributesToFunctions, \
    IndexingToFunctions, InplaceOperatorsToFunctions, OperatorsToFunctions, \
    ContainerLiteralsToFunctions
from .inspect_function import bind_arguments
from .inspect_name import get_func_module_name, get_func_qual_name
from .trace_event import TraceEvent, TraceValueEvent, TraceCall, TraceReturn, \
    TraceAccess, TraceAssign, TraceDelete

# Modules needed for tracer execution environment.
import operator
from . import operator as extra_operator


class Tracer(ASTTracer):
    """ Execution tracer for Python.
    
    The tracer executes Python code and emits trace events as the code runs.
    The trace events are consumed by the flow graph builder to create flow
    graphs.
    """
    
    # The most recent trace event. Read-only.
    event = Instance(TraceEvent, allow_none=True)
    
    # The trace call event stack. Read-only.
    stack = List(Instance(TraceCall))

    # Scope stack for currently executing code.
    _stack = Instance(deque, ()) # List(Instance(_ScopeItem))
    
    # Tracer interface

    def trace(self, code_or_node, codename=None, env=None):
        """ Execute and trace Python code.

        Parameters
        ----------
        code_or_node : str or ast.AST
            Python code to record
        
        codename : str (optional)
            Name of file from which code was loaded, if any.
            Passed to `compile`.
        
        env : dict (optional)
            Environment in which to execute code

        Returns
        -------
        Local environment in which code was executed
        """
        # Reset state.
        self.event = None
        self._stack.clear()
        self._stack.append(_ScopeItem())

        # Parse the code into AST.
        if isinstance(code_or_node, six.string_types):
            node = ast.parse(code_or_node)
            codename = codename or '<string>'
        elif isinstance(code_or_node, ast.AST):
            node = code_or_node
            codename = codename or '<ast>'
        else:
            raise TypeError("Code must be string or AST node")

        # Run AST transformers and compile code.
        node = self._transform_ast(node)
        ast.fix_missing_locations(node)
        compiled = compile(node, filename=codename, mode='exec')
        
        # Execute the code in the appropriate environment.
        env = env if env is not None else {}
        env.update(self._prepare_env())
        exec(compiled, env)
        return env
    
    # AST Tracer interface

    def _trace_function(self, function, nargs):
        """ Called after function object is evaluated.
        """
        scope = self._stack[-1]
        scope.call_stack.append(_CallItem(function=function, nargs=nargs))

        # If there are no arguments, the function will now be called.
        if nargs == 0:
            self._trace_call()

        return function
    
    def _trace_argument(self, arg_value, arg_name=None, nstars=0):
        """ Called after function argument is evaluated.
        """
        # Record argument(s) in appropriate place.
        scope = self._stack[-1]
        call = scope.call_stack[-1]
        if nstars == 0:
            if arg_name is None:
                call.arguments.append(arg_value)
            else:
                call.keywords[arg_name] = arg_value
        elif nstars == 1:
            call.arguments.extend(arg_value)
        elif nstars == 2:
            call.keywords.update(arg_value)
        else:
            raise ValueError("nstars must be 0, 1, or 2")

        # If this argument was the last, the function will now be called.
        call.nargs -= 1
        if call.nargs == 0:
            self._trace_call()
        
        return arg_value
    
    def _trace_call(self):
        """ Called immediately before function is called.
        """
        prev_scope = self._stack[-1]
        call = prev_scope.call_stack.pop()

        # Bind arguments to function.
        function = call.function
        arguments = bind_arguments(function, *call.arguments, **call.keywords)

        # Create call event.
        event = self._create_call_event(function, arguments)
        emit_events = prev_scope.emit_events and \
            not (prev_scope.event and prev_scope.event.atomic)
        if emit_events:
            self.event = event

        scope = _ScopeItem(event=event, emit_events=emit_events)
        self._stack.append(scope)
    
    def _trace_return(self, return_value, multiple_values=False):
        """ Called after function returns.
        """
        scope = self._stack.pop()

        # If we detect a compound assignment, coerce the return value to a
        # tuple. This is rather tricky. The change will not affect the semantics
        # of the program, but it will prevent the return sub-values from being
        # garbage collected unexpectedly when they are ephemeral objects, like
        # slices of a NumPy array.
        if multiple_values:
            try:
                return_value = tuple(return_value)
            except TypeError:
                # This will only fail when the return value is not iterable,
                # in which case the user has an error in their code that will
                # be raised shortly.
                pass

        # Create return event.
        event = self._create_return_event(
            scope.event, return_value, multiple_values)
        if scope.emit_events:
            self.event = event

        return event
    
    def _trace_access(self, name, value):
        """ Called after a variable is accessed.
        """
        scope = self._stack[-1]

        # Create access event.
        if scope.emit_events:
            self.event = event = TraceAccess(name=name, value=value)
            return event
        
        return value
    
    def _trace_assign(self, name, value):
        """ Called before a variable is assigned.
        """
        scope = self._stack[-1]

        if isinstance(value, TraceValueEvent):
            value_event = value
            value = value_event.value
        else:
            value_event = None

        # Create assign event.
        if scope.emit_events:
            self.event = event = TraceAssign(
                name=name, value=value, value_event=value_event)
            return event
        
        return value
    
    def _trace_delete(self, name):
        """ Called before a variable is deleted.
        """
        scope = self._stack[-1]
        if scope.emit_events:
            self.event = TraceDelete(name=name)
    
    # Protected interface

    def _prepare_env(self):
        """ Prepare the environment in which code will be excecuted.
        """
        env = dict(globals())
        env.update(dict(
            __operator__ = operator,
            __extra_operator__ = extra_operator,
            __trace__ = self,
        ))
        return env

    def _transform_ast(self, node):
        """ Transform AST to insert tracing machinery.
        """
        operator_name = '__operator__'
        transformers = [
            EliminateMultipleTargets(),
            AttributesToFunctions(),
            IndexingToFunctions(operator_name),
            OperatorsToFunctions(operator_name),
            InplaceOperatorsToFunctions(operator_name),
            ContainerLiteralsToFunctions('__extra_operator__'),
            ASTTraceTransformer('__trace__'),
        ]
        for transformer in transformers:
            transformer.visit(node)
        return node

    def _create_call_event(self, func, arguments):
        """ Create trace event for function call.
        """
        # Inspect the function.
        module_name = get_func_module_name(func)
        qual_name = get_func_qual_name(func)
        atomic = module_name != self.__class__.__module__

        # Unbox any trace events carrying argument values.
        argument_events = {}
        for arg_name, arg in arguments.items():
            if isinstance(arg, TraceValueEvent):
                arguments[arg_name] = arg.value
                argument_events[arg_name] = arg
        
        # Create function call event.
        return TraceCall(tracer=self, function=func, atomic=atomic,
                         module_name=module_name, qual_name=qual_name,
                         arguments=arguments, argument_events=argument_events)
    
    def _create_return_event(self, call_event, return_value, multiple_values):
        """ Create trace event for function return.
        """
        call = call_event
        return TraceReturn(tracer=self, function=call.function,
                           atomic=call.atomic, module_name=call.module_name,
                           qual_name=call.qual_name, arguments=call.arguments, 
                           value=return_value, multiple_values=multiple_values)


class _ScopeItem(HasTraits):
    """ Stack item for scope of currently executing code.
    """

    # Call event for currenting evaluating function call.
    # If None, we're at the top level.
    event = Instance(TraceCall, allow_none=True)

    # Whether to emit call and return events for this scope?
    emit_events = Bool(True)

    # Stack of evaluating function calls.
    call_stack = Instance(deque, ()) # List(Instance(_CallItem))


class _CallItem(HasTraits):
    """ Stack item for function calls in currently evaluating expression.
    """

    # Function object being called.
    function = Any()

    # Number of arguments in call expression yet to be recorded.
    nargs = Int()

    # Positional argument recorded so far.
    arguments = List()

    # Keyword arguments recorded so far.
    keywords = Instance(OrderedDict, ())
