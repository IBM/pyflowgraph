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

""" Record flow graphs by running Python code.

This module is a convenient entry point for users of the package, wrapping
the `FlowGraphBuilder` and `Tracer` into easy-to-use functions.
"""
from __future__ import absolute_import

from traitlets import HasTraits, Instance

from flowgraph.trace.tracer import Tracer
from .flow_graph_builder import FlowGraphBuilder


class Recorder(HasTraits):
    """ Context manager to record flow graphs.

    Like all context managers, this class should be used in a `with` statement::

        with Recorder() as graph:
            [...]
    """
    builder = Instance(FlowGraphBuilder)
    tracer = Instance(Tracer)

    # Context manager interface
    
    def __enter__(self):
        self.tracer.observe(self._handle_trace_event, 'event')
        self.tracer.enable()
        return self.builder.graph
        
    def __exit__(self, type, value, traceback):
        self.tracer.disable()
        self.tracer.unobserve(self._handle_trace_event, 'event')

    # Handlers

    def _handle_trace_event(self, changed):
        event = changed['new']
        if event:
            self.builder.push_event(event)