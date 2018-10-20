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

""" Command-line interface to pyflowgraph.
"""
from __future__ import absolute_import

import six
import sys

import click

from .core.flow_graph import flow_graph_to_graphml
from .core.graphml import write_graphml
from .core.record import record_code


@click.command()
@click.argument('script', type=click.File('r'))
@click.option('-o', '--out', type=click.File('wb'))
def cli(script, out):
    code = script.read()
    graph = record_code(code)

    out = out or (sys.stdout.buffer if six.PY3 else sys.stdout)
    write_graphml(flow_graph_to_graphml(graph), out)
