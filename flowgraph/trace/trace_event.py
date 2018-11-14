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

from collections import OrderedDict

from traitlets import HasTraits, Any, Bool, Dict, Instance, List, Unicode

from .ast_tracer import BoxedValue


class TraceEvent(HasTraits):
    """ Event generated when tracing the execution of Python code.
    """
    
    # Tracer that created this event.
    tracer = Instance('flowgraph.trace.tracer.Tracer')


class TraceFunctionEvent(TraceEvent):
    """ Event pertaining to a function call.
    """
    
    # The function object (any callable).
    function = Any()
    
    # Name of module containing the definition of the function.
    # E.g., 'collections' or 'flowgraph.userlib.data.read_data'.
    module_name = Unicode()
    
    # Qualified name of function.
    # E.g., 'map' or 'OrderedDict.__init__'.
    qual_name = Unicode()
    
    # Whether the function is "atomic", i.e., its body will not be traced.
    atomic = Bool()
    
    @property
    def name(self):
        """ Short name of function.
        """
        return self.qual_name.split('.')[-1]
    
    @property
    def full_name(self):
        """ Full name of function.
        """
        return self.module_name + '.' + self.qual_name


class TraceValueEvent(TraceEvent, BoxedValue):
    """ Event pertaining to an expression that produces a value.

    The value produced by the expression is stored in the `value` attribute.
    """


class TraceCall(TraceFunctionEvent):
    """ Event generated immediately before a function is called.
    """
    
    # Mapping from argument name to argument value.
    # The ordering of the arguments is that of the function definition.
    arguments = Instance(OrderedDict)

    # Mapping from argument name to argument's parent event, if any.
    argument_events = Dict()


class TraceReturn(TraceFunctionEvent, TraceValueEvent):
    """ Event generated immediately after a function returns.

    The return value is stored in the `value` attribute.
    """
    
    # Map from argument name to argument value.
    # Warning: if an argument has pass-by-reference semantics (as most types
    # in Python do), the argument may be mutated from its state in the 
    # corresponding call event.
    arguments = Instance(OrderedDict)


class TraceAccess(TraceValueEvent):
    """ Event generated immediately after a variable is accessed.

    The variable's value is stored in the `value` attribute.
    """

    # Name of variable that was accessed.
    name = Unicode()


class TraceAssign(TraceValueEvent):
    """ Event generated immediately before a variable is assigned.

    The value to be assigned is stored in the `value` attribute.
    """

    # Names of variables to be assigned.
    names = List()

    # Parent event of value, if any.
    value_event = Instance(TraceValueEvent, allow_none=True)


# XXX: Trait change notifications for `return_value` can lead to FutureWarning
# from numpy: http://stackoverflow.com/questions/28337085
import warnings
warnings.simplefilter(action='ignore', category=FutureWarning)
