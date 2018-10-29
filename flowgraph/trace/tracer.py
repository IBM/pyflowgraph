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
import operator
import six
import types

from traitlets import HasTraits, Bool, Dict, Instance, Int, List, Unicode

from .ast_trace import  WrapCalls, make_tracing_call_wrapper
from .ast_transform import AttributesToFunctions, IndexingToFunctions, \
    OperatorsToFunctions
from .inspect_names import get_func_module_name, get_func_qual_name
from .object_tracker import ObjectTracker
from .trace_event import TraceEvent, TraceCall, TraceReturn


class Tracer(HasTraits):
    """ Execution tracer for Python.
    
    The tracer executes Python code and emits trace events as the code runs.
    The trace events are consumed by the flow graph builder to create flow
    graphs.
    """
    
    # The most recent trace event. Read-only.
    # XXX: In Enthought traits, this would be an Event trait.
    event = Instance(TraceEvent, allow_none=True)
    
    # The trace call event stack. Read-only.
    stack = List(Instance(TraceCall))
    
    # Tracks objects using weak references.
    object_tracker = Instance(ObjectTracker, args=())
    
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
            Local environment in which to execute code

        Returns
        -------
        Local environment in which code was executed
        """
        # Reset state.
        self.event = None
        self.stack = []

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
        
        # Execute the code in an appropriate environment.
        global_env = dict(globals())
        global_env.update(self._prepare_env())
        local_env = env if env is not None else {}
        exec(compiled, global_env, local_env)
        return local_env
    
    def track_object(self, obj):
        """ Start tracking an object.
        """
        return self.object_tracker.track(obj)
    
    # Protected interface

    def _prepare_env(self):
        """ Prepare the global environment in which code will be excecuted.
        """
        return dict(
            __operator__ = operator,
            __trace__ = make_tracing_call_wrapper(
                on_call = self._on_function_call,
                on_return = self._on_function_return,
                filter_call = self._filter_call,
            ),
        )

    def _transform_ast(self, node):
        """ Transform AST to insert tracing machinery.
        """
        transformers = [
            AttributesToFunctions(),
            IndexingToFunctions('__operator__'),
            OperatorsToFunctions('__operator__'),
            WrapCalls('__trace__'),
        ]
        for transformer in transformers:
            transformer.visit(node)
        return node

    def _on_function_call(self, func, arguments):
        """ Handle function calls during tracing.
        """
        # Inspect the function.
        module_name = get_func_module_name(func)
        qual_name = get_func_qual_name(func)
        atomic = True
            
        # Track every argument that is trackable.
        for arg in arguments.values():
            if self.object_tracker.is_trackable(arg):
                self.track_object(arg)
        
        # Push the call event.
        self.event = TraceCall(tracer=self, function=func, atomic=atomic,
                               module_name=module_name, qual_name=qual_name,
                               arguments=arguments)
        self.stack.append(self.event)
    
    def _on_function_return(self, func, arguments, return_value):
        """ Handle function returns during tracing.
        """
         # Track the return value(s), if possible.
        if isinstance(return_value, tuple):
            # Treat tuple return value as multiple return values.
            for value in return_value:
                if self.object_tracker.is_trackable(value):
                    self.track_object(value)
        elif self.object_tracker.is_trackable(return_value):
            self.track_object(return_value)

        # Pop the corresponding call event and set return event.
        call = self.stack.pop()
        self.event = TraceReturn(tracer=self, function=func, atomic=call.atomic,
                                 module_name=call.module_name,
                                 qual_name=call.qual_name,
                                 arguments=arguments, return_value=return_value)
    
    def _filter_call(self, func, arguments):
        """ Whether to emit trace events for function call (and return).
        """
        if func is getattr:
            # Ignore attribute access on modules.
            first = next(iter(arguments.values()))
            return not isinstance(first, types.ModuleType)

        return True
