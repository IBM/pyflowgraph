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

import os

from traitlets import HasTraits, Instance

from flowgraph.trace.tracer import Tracer
from .flow_graph import flow_graph_to_graphml
from .flow_graph_builder import FlowGraphBuilder
from .graphml import write_graphml
from .remote_annotation_db import RemoteAnnotationDB


def record_code(code, out=None, env=None, cwd=None, db=None, **kwargs):
    """ Evaluate and record Python code.

    Parameters
    ----------
    code : str or code object
        Python code to record
    
    out : str or file-like object (optional)
        Filename or file to which recorded flow graph is written (as GraphML)
    
    env : dict (optional)
        Environment in which to evaluate code

    cwd : str (optional)
        Current working directory in which to evaluate code
    
    db : AnnotatioDB (optional)
        Annotation database, by default the standard remoate annotation DB

    **kwargs
        Extra arguments to pass to `FlowGraphBuilder`.
    """
    db = db or RemoteAnnotationDB.from_library_config()
    builder = FlowGraphBuilder(**kwargs)
    builder.annotator.db = db
    tracer = Tracer(modules=['__record__'])

    # Evaluate the code with the right working directory, environment, and
    # module name.
    env = env or {}
    env['__name__'] = '__record__'
    if cwd is not None:
        oldcwd = os.getcwd()
        os.chdir(cwd)
    try:
        with Recorder(builder=builder, tracer=tracer) as graph:
            exec(code, env)
    finally:
        if cwd is not None:
            os.chdir(oldcwd)
    
    if out is not None:
        write_graphml(flow_graph_to_graphml(graph), out)

    return graph


def record_script(filename, **kwargs):
    """ Evaluate and record a Python script.

    Parameters
    ----------
    filename : str
        Filename of Python script to evaluate
    
    **kwargs
        Extra arguments to pass to `record_code`.
    """
    # Read and compile the script.
    with open(filename) as f:
        code = compile(f.read(), filename, 'exec')
    
    return record_code(code, **kwargs)


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