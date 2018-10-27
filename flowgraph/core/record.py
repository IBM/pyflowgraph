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


def record_code(code, codename=None, out=None, env=None, cwd=None, db=None,
                tracer=None, simplify_outputs=True, **kwargs):
    """ Execute and record Python code.

    Parameters
    ----------
    code : str or ast.AST
        Python code to record
    
    codename : str (optional)
        Name of file from which code was loaded, if any.
        Passed to `compile`.
    
    out : str or file-like object (optional)
        Filename or file to which recorded flow graph is written (as GraphML)
    
    env : dict (optional)
        Local environment in which to execute code

    cwd : str (optional)
        Current working directory in which to execute code
    
    db : AnnotationDB (optional)
        Annotation database, by default the standard remoate annotation DB
    
    tracer : Tracer (optional)
        Execution tracer, which includes the object tracker
    
    simplify_outputs : bool (optional)
        Whether to simplify outputs when writing GraphML

    **kwargs
        Extra arguments to pass to `FlowGraphBuilder`
    """
    # Set up flow graph builder.
    db = db or RemoteAnnotationDB.from_library_config()
    builder = FlowGraphBuilder(**kwargs)
    builder.annotator.db = db

    # Set up tracer.
    def handle_trace_event(changed):
        event = changed['new']
        if event:
            builder.push_event(event)
    tracer = tracer or Tracer()

    # Evaluate the code in the right working directory and environment.
    if cwd is not None:
        oldcwd = os.getcwd()
        os.chdir(cwd)
    tracer.observe(handle_trace_event, 'event')
    try:
        tracer.trace(code, codename=codename, env=env)
    finally:
        tracer.unobserve(handle_trace_event, 'event')
        if cwd is not None:
            os.chdir(oldcwd)
    graph = builder.graph

    if out is not None:
        graphml = flow_graph_to_graphml(graph, simplify_outputs=simplify_outputs)
        write_graphml(graphml, out)

    return graph


def record_script(filename, **kwargs):
    """ Execute and record a Python script.

    Parameters
    ----------
    filename : str
        Filename of Python script to execute
    
    **kwargs
        Extra arguments to pass to `record_code`
    """
    # Read the script.
    with open(filename) as f:
        code = f.read()
    
    return record_code(code, codename=filename, **kwargs)
