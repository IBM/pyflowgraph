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

from traitlets import HasTraits, Any, Bool, Instance, Unicode


class TraceEvent(HasTraits):
    """ Event generated when tracing the execution of Python code.
    """
    
    # Tracer that created this event.
    tracer = Instance('flowgraph.trace.tracer.Tracer')
    
    # The function object that was called.
    function = Any()
    
    # Name of module containing the definition of the called function.
    # E.g., 'collections' or 'flowgraph.userlib.data.read_data'.
    module = Unicode()
    
    # Qualified name of the called function.
    # E.g., 'map' or 'OrderedDict.__init__'.
    qual_name = Unicode()
    
    # Whether the function call is "atomic", i.e., its body will not be traced.
    atomic = Bool()
    
    @property
    def name(self):
        """ Short name of the called function.
        """
        return self.qual_name.split('.')[-1]
    
    @property
    def full_name(self):
        """ Full name of the called function.
        """
        return self.module + '.' + self.qual_name


class TraceCall(TraceEvent):
    """ Event generated at the beginning of a function call.
    """
    
    # Map: argument name -> argument value.
    # The ordering of the arguments is that of the function definition.
    arguments = Instance(OrderedDict)


class TraceReturn(TraceEvent):
    """ Event generated when a function returns.
    """
    
    # Map: argument name -> argument value.
    # Warning: if an argument has pass-by-reference semantics (as most types
    # in Python do), the argument may be mutated from its state in the 
    # corresponding call event.
    arguments = Instance(OrderedDict)
    
    # Return value of function.
    return_value = Any()


# XXX: Trait change notifications for `return_value` can lead to FutureWarning
# from numpy: http://stackoverflow.com/questions/28337085
import warnings
warnings.simplefilter(action='ignore', category=FutureWarning)