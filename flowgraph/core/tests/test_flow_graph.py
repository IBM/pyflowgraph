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
from pathlib2 import Path
import six
from textwrap import dedent
import unittest

import networkx as nx
import networkx.algorithms.isomorphism as iso

from ..annotation_db import AnnotationDB
from ..flow_graph import new_flow_graph, flatten, join, \
    flow_graph_to_graphml, flow_graph_from_graphml
from ..graphutil import find_node
from ..graphml import read_graphml_str, write_graphml_str
from ..record import record_code
from ...trace.tracer import Tracer
from . import objects


class TestFlowGraph(unittest.TestCase):
    """ Tests for Python flow graph machinery.
    """

    @classmethod
    def setUpClass(cls):
        """ Set up the annotation DB and tracer.
        """
        objects_path = Path(objects.__file__).parent
        json_path = objects_path.joinpath('data', 'annotations.json')
        cls.db = AnnotationDB()
        cls.db.load_file(str(json_path))
        cls.tracer = Tracer()

    def record(self, code, env=None, **kwargs):
        """ Record block of code for test.
        """
        self.env = env if env is not None else {}
        self.env.update(dict(objects=objects))
        return record_code(dedent(code), db=self.db, tracer=self.tracer,
                           env=self.env, **kwargs)
    
    def id(self, name):
        """ Convenience method to get ID for tracked object.
        """
        obj = self.env[name]
        return self.tracer.object_tracker.get_id(obj)
    
    def assert_isomorphic(self, g1, g2, check_id=True):
        """ Assert that two flow graphs are isomorphic.
        """
        node_attrs = [ 'qual_name', 'slot' ]
        node_defaults = [ None ] * len(node_attrs)
        if check_id:
            edge_attrs = [ 'id', 'sourceport', 'targetport' ]
        else:
            edge_attrs = [ 'sourceport', 'targetport' ]
        edge_defaults = [ None ] * len(edge_attrs)
        
        node_match = iso.categorical_node_match(node_attrs, node_defaults)
        edge_match = iso.categorical_multiedge_match(edge_attrs, edge_defaults)
        self.assertTrue(nx.is_isomorphic(
            g1, g2, node_match=node_match, edge_match=edge_match))
    
    def get_ports(self, graph, node, portkind=None):
        """ Convenience method to get ports from node in flow graph.
        """
        ports = graph.nodes[node]['ports']
        if portkind is not None:
            ports = OrderedDict((p, data) for p, data in ports.items()
                                if data['portkind'] == portkind)
        return ports
    
    def test_two_object_flow(self):
        """ Check a simple, two-object flow.
        """
        actual = self.record("""
            foo = objects.Foo()
            bar = objects.bar_from_foo(foo)
        """)
        
        target = new_flow_graph()
        outputs = target.graph['output_node']
        target.add_node('1', qual_name='Foo')
        target.add_node('2', qual_name='bar_from_foo')
        target.add_edge('1', '2', id=self.id('foo'),
                        sourceport='__return__', targetport='foo')
        target.add_edge('1', outputs, id=self.id('foo'), sourceport='__return__')
        target.add_edge('2', outputs, id=self.id('bar'), sourceport='__return__')
        self.assert_isomorphic(actual, target)
    
    def test_two_object_flow_external(self):
        """ Check a simple, two-object flow with input from external object.
        """
        env = dict(foo = objects.Foo())
        actual = self.record("""
            bar = objects.bar_from_foo(foo)
        """, env=env)
        
        target = new_flow_graph()
        inputs, outputs = target.graph['input_node'], target.graph['output_node']
        target.add_node('1', qual_name='bar_from_foo')
        target.add_edge(inputs, '1', id=self.id('foo'), targetport='foo')
        target.add_edge('1', outputs, id=self.id('bar'), sourceport='__return__')
        self.assert_isomorphic(actual, target)
    
    def test_two_object_flow_untrackable_compose(self):
        """ Check a two-object flow with untrackable objects passed by
        composition.
        """
        actual = self.record("x = sum(range(5))")
        target = new_flow_graph()
        target.add_node('range', qual_name='range')
        target.add_node('sum', qual_name='sum')
        target.add_edge('range', 'sum', sourceport='__return__',
                        targetport='iterable' if six.PY3 else '0')
        self.assert_isomorphic(actual, target)
    
    def test_three_object_flow(self):
        """ Check a simple, three-object flow.
        """
        actual = self.record("""
            foo = objects.Foo()
            bar = objects.bar_from_foo(foo)
            baz = objects.baz_from_bar(bar)
        """)
        
        target = new_flow_graph()
        outputs = target.graph['output_node']
        target.add_node('1', qual_name='Foo')
        target.add_node('2', qual_name='bar_from_foo')
        target.add_node('3', qual_name='baz_from_bar')
        target.add_edge('1', '2', id=self.id('foo'),
                        sourceport='__return__', targetport='foo')
        target.add_edge('2', '3', id=self.id('bar'),
                        sourceport='__return__', targetport='bar')
        target.add_edge('1', outputs, id=self.id('foo'), sourceport='__return__')
        target.add_edge('2', outputs, id=self.id('bar'), sourceport='__return__')
        target.add_edge('3', outputs, id=self.id('baz'), sourceport='__return__')
        self.assert_isomorphic(actual, target)
    
    def test_nonpure_flow(self):
        """ Test that pure and non-pure functions are handled differently.
        """
        actual = self.record("""
            foo = objects.Foo()
            bar = objects.bar_from_foo_mutating(foo)
            baz = objects.baz_from_foo(foo)
        """)
        
        target = new_flow_graph()
        outputs = target.graph['output_node']
        target.add_node('1', qual_name='Foo')
        target.add_node('2', qual_name='bar_from_foo_mutating')
        target.add_node('3', qual_name='baz_from_foo')
        target.add_edge('1', '2', id=self.id('foo'),
                        sourceport='__return__', targetport='foo')
        target.add_edge('2', '3', id=self.id('foo'),
                        sourceport='foo!', targetport='foo')
        target.add_edge('2', outputs, id=self.id('foo'), sourceport='foo!')
        target.add_edge('2', outputs, id=self.id('bar'), sourceport='__return__')
        target.add_edge('3', outputs, id=self.id('baz'), sourceport='__return__')
        self.assert_isomorphic(actual, target)
    
    def test_pure_flow(self):
        """ Test that pure and non-pure functions are handled differently.
        """
        actual = self.record("""
            foo = objects.Foo()
            bar = objects.bar_from_foo(foo)
            baz = objects.baz_from_foo(foo)
        """)
        
        target = new_flow_graph()
        outputs = target.graph['output_node']
        target.add_node('1', qual_name='Foo')
        target.add_node('2', qual_name='bar_from_foo')
        target.add_node('3', qual_name='baz_from_foo')
        target.add_edge('1', '2', id=self.id('foo'),
                        sourceport='__return__', targetport='foo')
        target.add_edge('1', '3', id=self.id('foo'),
                        sourceport='__return__', targetport='foo')
        target.add_edge('1', outputs, id=self.id('foo'), sourceport='__return__')
        target.add_edge('2', outputs, id=self.id('bar'), sourceport='__return__')
        target.add_edge('3', outputs, id=self.id('baz'), sourceport='__return__')
        self.assert_isomorphic(actual, target)
    
    def test_class_methods(self):
        """ Test that class methods are represented correctly.
        """
        actual =self.record("""
            bar = objects.Bar.make_bar()
        """)
        
        target = new_flow_graph()
        outputs = target.graph['output_node']
        target.add_node('1', qual_name='Bar.make_bar')
        target.add_edge('1', outputs, id=self.id('bar'), sourceport='__return__')
        self.assert_isomorphic(actual, target)
    
    def test_singly_nested(self):
        """ Test that nested function calls are mapped to a nested subgraph.
        """
        actual = self.record("""
            def outer_bar():
                foo = objects.Foo()
                return objects.bar_from_foo(foo)

            bar = outer_bar()
        """)
        
        target = new_flow_graph()
        outputs = target.graph['output_node']
        target.add_node('1', qual_name='outer_bar')
        target.add_edge('1', outputs, id=self.id('bar'), sourceport='__return__')
        self.assert_isomorphic(actual, target)
        
        node = find_node(actual, lambda n: n.get('qual_name') == 'outer_bar')
        actual_sub = actual.nodes[node]['graph']
        target_sub = new_flow_graph()
        outputs = target_sub.graph['output_node']
        target_sub.add_node('1', qual_name='Foo')
        target_sub.add_node('2', qual_name='bar_from_foo')
        target_sub.add_edge('1', '2', sourceport='__return__', targetport='foo')
        target_sub.add_edge('1', outputs, sourceport='__return__')
        target_sub.add_edge('2', outputs, sourceport='__return__')
        self.assert_isomorphic(actual_sub, target_sub, check_id=False)
    
    def test_flatten_singly_nested(self):
        """ Test that a singly nested function call can be flattened.
        """
        graph = self.record("""
            def outer_bar():
                foo = objects.Foo()
                return objects.bar_from_foo(foo)

            bar = outer_bar()
        """)
        
        actual = flatten(graph)
        target = new_flow_graph()
        outputs = target.graph['output_node']
        target.add_node('1', qual_name='Foo')
        target.add_node('2', qual_name='bar_from_foo')
        target.add_edge('1', '2', sourceport='__return__', targetport='foo')
        target.add_edge('2', outputs, sourceport='__return__')
        self.assert_isomorphic(actual, target, check_id=False)
    
    def test_doubly_nested(self):
        """ Test that doubly nested function calls are handled.
        """
        actual = self.record("""
            def inner_bar_from_foo(foo):
                return objects.bar_from_foo(foo)

            def outer_bar_from_foo(foo):
                return inner_bar_from_foo(foo)

            foo = objects.Foo()
            bar = outer_bar_from_foo(foo)
        """)
        
        target = new_flow_graph()
        outputs = target.graph['output_node']
        target.add_node('1', qual_name='Foo')
        target.add_node('2', qual_name='outer_bar_from_foo')
        target.add_edge('1', '2', id=self.id('foo'),
                        sourceport='__return__', targetport='foo')
        target.add_edge('1', outputs, id=self.id('foo'), sourceport='__return__')
        target.add_edge('2', outputs, id=self.id('bar'), sourceport='__return__')
        self.assert_isomorphic(actual, target)
        
        node = find_node(actual, lambda n: n.get('qual_name') == 'outer_bar_from_foo')
        actual_sub1 = actual.nodes[node]['graph']
        target_sub1 = new_flow_graph()
        inputs = target_sub1.graph['input_node']
        outputs = target_sub1.graph['output_node']
        target_sub1.add_node('1', qual_name='inner_bar_from_foo')
        target_sub1.add_edge(inputs, '1', id=self.id('foo'), targetport='foo')
        target_sub1.add_edge('1', outputs, id=self.id('bar'), sourceport='__return__')
        self.assert_isomorphic(actual_sub1, target_sub1)
        
        node = find_node(actual_sub1, lambda n: n.get('qual_name') == 'inner_bar_from_foo')
        actual_sub2 = actual_sub1.nodes[node]['graph']
        target_sub2 = new_flow_graph()
        inputs = target_sub2.graph['input_node']
        outputs = target_sub2.graph['output_node']
        target_sub2.add_node('1', qual_name='bar_from_foo')
        target_sub2.add_edge(inputs, '1', id=self.id('foo'), targetport='foo')
        target_sub2.add_edge('1', outputs, id=self.id('bar'), sourceport='__return__')
        self.assert_isomorphic(actual_sub2, target_sub2)
    
    def test_flatten_doubly_nested(self):
        """ Test that doubly nested function calls can be flattened.
        """
        graph = self.record("""
            def inner_bar_from_foo(foo):
                return objects.bar_from_foo(foo)

            def outer_bar_from_foo(foo):
                return inner_bar_from_foo(foo)

            foo = objects.Foo()
            bar = outer_bar_from_foo(foo)
        """)
            
        actual = flatten(graph)
        target = new_flow_graph()
        outputs = target.graph['output_node']
        target.add_node('1', qual_name='Foo')
        target.add_node('2', qual_name='bar_from_foo')
        target.add_edge('1', '2', id=self.id('foo'),
                        sourceport='__return__', targetport='foo')
        target.add_edge('1', outputs, id=self.id('foo'), sourceport='__return__')
        target.add_edge('2', outputs, id=self.id('bar'), sourceport='__return__')
        self.assert_isomorphic(actual, target)
    
    def test_attributes_methods(self):
        """ Test that attribute accesses and method calls are traced.
        """
        actual = self.record("""
            foo = objects.Foo()
            x = foo.x
            y = foo.y
            foo_sum = foo.do_sum()
            foo_prod = foo.do_prod()
        """)
        
        target = new_flow_graph()
        outputs = target.graph['output_node']
        target.add_node('1', qual_name='Foo')
        target.add_node('x', qual_name='getattr', slot='x')
        target.add_node('y', qual_name='getattr', slot='y')
        target.add_node('sum', qual_name='Foo.do_sum')
        target.add_node('prod', qual_name='Foo.do_prod')
        target.add_edge('1', 'x', id=self.id('foo'),
                        sourceport='__return__', targetport='0')
        target.add_edge('1', 'y', id=self.id('foo'),
                        sourceport='__return__', targetport='0')
        target.add_edge('1', 'sum', id=self.id('foo'),
                        sourceport='__return__', targetport='self')
        target.add_edge('1', 'prod', id=self.id('foo'),
                        sourceport='__return__', targetport='self')
        target.add_edge('1', outputs, id=self.id('foo'), sourceport='__return__')
        self.assert_isomorphic(actual, target)
    
    def test_higher_order_function(self):
        """ Test that higher-order functions using user-defined functions work.
        """
        actual = self.record("""
            foo = objects.Foo()
            foo.apply(lambda x: objects.Bar(x))
        """)
        
        target = new_flow_graph()
        outputs = target.graph['output_node']
        target.add_node('1', qual_name='Foo')
        target.add_node('2', qual_name='Foo.apply')
        target.add_edge('1', '2', id=self.id('foo'),
                        sourceport='__return__', targetport='self')
        target.add_edge('1', outputs, id=self.id('foo'), sourceport='__return__')
        self.assert_isomorphic(actual, target)
    
    @unittest.skip("Static analysis for sequence literals not implemented")
    def test_track_inside_list(self):
        """ Test a function call with tracked objects inside a list.
        """
        actual = self.record("""
            foo1 = objects.Foo()
            foo2 = objects.Foo()
            foos = [foo1, foo2]
            objects.foo_x_sum(foos)
        """)
        
        target = new_flow_graph()
        outputs = target.graph['output_node']
        target.add_node('1', qual_name='Foo')
        target.add_node('2', qual_name='Foo')
        target.add_node('3', qual_name='foo_x_sum')
        target.add_edge('1', '3', id=self.id('foo1'),
                        sourceport='__return__', targetport='foos')
        target.add_edge('2', '3', id=self.id('foo2'),
                        sourceport='__return__', targetport='foos')
        target.add_edge('1', outputs, id=self.id('foo1'), sourceport='__return__')
        target.add_edge('2', outputs, id=self.id('foo2'), sourceport='__return__')
        self.assert_isomorphic(actual, target)
    
    def test_function_annotations(self):
        """ Test that function annotations are stored on nodes.
        """
        graph = self.record("""
            foo = objects.create_foo()
            bar = objects.bar_from_foo(foo)
        """)

        node = find_node(graph, lambda n: n.get('qual_name') == 'create_foo')
        actual = graph.nodes[node]
        actual.pop('ports', None)
        desired = {
            'module': 'flowgraph.core.tests.objects',
            'qual_name': 'create_foo',
            'annotation': 'python/flowgraph/create-foo',
            'annotation_kind': 'function',
        }
        self.assertEqual(actual, desired)
        
        node = find_node(graph, lambda n: n.get('qual_name') == 'bar_from_foo')
        note = graph.nodes[node]['annotation']
        actual = graph.nodes[node]
        actual.pop('ports', None)
        desired = {
            'module': 'flowgraph.core.tests.objects',
            'qual_name': 'bar_from_foo',
            'annotation': 'python/flowgraph/bar-from-foo',
            'annotation_kind': 'function',
        }
        self.assertEqual(actual, desired)
    
    def test_object_annotations(self):
        """ Test that object annotations are stored on edges.
        """
        graph = self.record("""
            foo = objects.create_foo()
            bar = objects.bar_from_foo(foo)
        """)
            
        output_node = graph.graph['output_node']
        foo_node = find_node(graph, lambda n: n.get('qual_name') == 'create_foo')
        bar_node = find_node(graph, lambda n: n.get('qual_name') == 'bar_from_foo')
        
        actual = graph.edges[foo_node, bar_node, 0]
        desired = {
            'sourceport': '__return__',
            'targetport': 'foo',
            'id': self.id('foo'),
            'annotation': 'python/flowgraph/foo',
        }
        self.assertEqual(actual, desired)
        
        actual = graph.edges[bar_node, output_node, 0]
        desired = {
            'sourceport': '__return__',
            'id': self.id('bar'),
            'annotation': 'python/flowgraph/bar',
        }
        self.assertEqual(actual, desired)
    
    def test_constructor_annotations(self):
        """ Test that constructors of annotated objects are annotated.
        """
        graph = self.record("""
            foo = objects.Foo()
        """)
        
        node = find_node(graph, lambda n: n.get('qual_name') == 'Foo')
        actual = graph.nodes[node]
        actual.pop('ports', None)
        desired = {
            'module': 'flowgraph.core.tests.objects',
            'qual_name': 'Foo',
            'annotation': 'python/flowgraph/foo',
            'annotation_kind': 'construct',
        }
        self.assertEqual(actual, desired)
    
    def test_input_ports(self):
        """ Test that data for input ports is stored.
        """
        graph = self.record("""
            foo = objects.create_foo()
            bar = objects.bar_from_foo(foo, 10)
        """)
        
        node = find_node(graph, lambda n: n.get('qual_name') == 'bar_from_foo')
        actual = self.get_ports(graph, node, 'input')
        desired = OrderedDict([
            ('foo', {
                'argname': 'foo',
                'portkind': 'input',
                'module': 'flowgraph.core.tests.objects',
                'qual_name': 'Foo',
                'annotation': 'python/flowgraph/foo',
                'annotation_index': 1,
                'id': self.id('foo'),
            }),
            ('x', {
                'argname': 'x',
                'portkind': 'input',
                'annotation': 'python/builtins/int',
                'annotation_index': 2,
                'value': 10,
            })
        ])
        self.assertEqual(actual, desired)
    
    def test_input_ports_varargs(self):
        """ Test that varargs and keyword arguments are stored.
        """
        graph = self.record("""
            objects.sum_varargs(1,2,3,w=4)
        """)
        
        node = find_node(graph, lambda n: n.get('qual_name') == 'sum_varargs')
        actual = self.get_ports(graph, node, 'input')
        desired = OrderedDict([
            ('x', {
                'argname': 'x',
                'portkind': 'input',
                'annotation': 'python/builtins/int',
                'value': 1,
            }),
            ('y', {
                'argname': 'y',
                'portkind': 'input',
                'annotation': 'python/builtins/int',
                'value': 2,
            }),
            ('args', {
                'argname': 'args',
                'portkind': 'input',
                'value': (3,),
            }),
            ('kw', {
                'argname': 'kw',
                'portkind': 'input',
                'value': {'w': 4},
            })
        ])
        self.assertEqual(actual, desired)
    
    def test_output_data(self):
        """ Test that data for output ports is stored.
        """
        graph = self.record("""
            foo = objects.create_foo()
            x = foo.do_sum()
        """)
        
        node = find_node(graph, lambda n: n.get('qual_name') == 'Foo.do_sum')
        actual = self.get_ports(graph, node, 'output')
        desired = OrderedDict([
            ('__return__', {
                'argname': '__return__',
                'portkind': 'output',
                'annotation': 'python/builtins/int',
                'annotation_index': 1,
                'value': self.env['x'],
            })
        ])
        self.assertEqual(actual, desired)
        
        node = find_node(graph, lambda n: n.get('qual_name') == 'create_foo')
        actual = self.get_ports(graph, node, 'output')
        desired = OrderedDict([
            ('__return__', {
                'argname': '__return__',
                'portkind': 'output',
                'module': 'flowgraph.core.tests.objects',
                'qual_name': 'Foo',
                'annotation': 'python/flowgraph/foo',
                'annotation_index': 1,
                'id': self.id('foo'),
            })
        ])
        self.assertEqual(actual, desired)
    
    def test_output_data_mutating(self):
        """ Test that output ports are created for mutated arguments.
        """
        graph = self.record("""
            foo = objects.Foo()
            bar = objects.bar_from_foo_mutating(foo)
        """)
            
        node = find_node(graph, lambda n: n.get('qual_name') == 'bar_from_foo_mutating')
        actual = self.get_ports(graph, node, 'output')
        desired = OrderedDict([
            ('__return__', {
                'argname': '__return__',
                'portkind': 'output',
                'module': 'flowgraph.core.tests.objects',
                'qual_name': 'Bar',
                'annotation': 'python/flowgraph/bar',
                'annotation_index': 2,
                'id': self.id('bar'),
            }),
            ('foo!', {
                'argname': 'foo',
                'portkind': 'output',
                'module': 'flowgraph.core.tests.objects',
                'qual_name': 'Foo',
                'annotation': 'python/flowgraph/foo',
                'annotation_index': 1,
                'id': self.id('foo'),
            }),
        ])
        self.assertEqual(actual, desired)
    
    def test_multiple_outputs(self):
        """ Test that multiple outputs are created for tuple return values.
        """
        graph = self.record("""
            foo, bar = objects.create_foo_and_bar()
        """)
        
        target = new_flow_graph()
        outputs = target.graph['output_node']
        target.add_node('1', qual_name='create_foo_and_bar')
        target.add_edge('1', outputs, id=self.id('foo'), sourceport='__return__.0')
        target.add_edge('1', outputs, id=self.id('bar'), sourceport='__return__.1')
        self.assert_isomorphic(graph, target)
        
        node = find_node(graph, lambda n: n.get('qual_name') == 'create_foo_and_bar')
        actual = self.get_ports(graph, node, 'output')
        desired = OrderedDict([
            ('__return__.0', {
                'argname': '__return__.0',
                'portkind': 'output',
                'module': 'flowgraph.core.tests.objects',
                'qual_name': 'Foo',
                'annotation': 'python/flowgraph/foo',
                'id': self.id('foo'),
            }),
            ('__return__.1', {
                'argname': '__return__.1',
                'portkind': 'output',
                'module': 'flowgraph.core.tests.objects',
                'qual_name': 'Bar',
                'annotation': 'python/flowgraph/bar',
                'id': self.id('bar'),
            }),
        ])
        self.assertEqual(actual, desired)
    
    def test_object_slots_disabled(self):
        """ Test that capture of annotated object slots can be disabled.
        """
        actual = self.record("""
            foo = objects.FooSlots()
        """, store_slots=False)
        
        target = new_flow_graph()
        outputs = target.graph['output_node']
        target.add_node('1', qual_name='FooSlots')
        target.add_edge('1', outputs, id=self.id('foo'), sourceport='__return__')
        self.assert_isomorphic(actual, target)
    
    def test_object_slots_track_getattr(self):
        """ Test that annotated object slots are captured on explicit getattrs.
        """
        graph = self.record("""
            foo = objects.FooSlots()
            x = foo.x
            y = foo.y
        """, store_slots=False)
        
        actual = graph
        target = new_flow_graph()
        outputs = target.graph['output_node']
        target.add_node('foo', qual_name='FooSlots')
        target.add_node('x', qual_name='getattr', slot='x')
        target.add_node('y', qual_name='getattr', slot='y')
        target.add_edge('foo', 'x', id=self.id('foo'),
                        sourceport='__return__', targetport='0')
        target.add_edge('foo', 'y', id=self.id('foo'),
                        sourceport='__return__', targetport='0')
        target.add_edge('foo', outputs, id=self.id('foo'), sourceport='__return__')
        self.assert_isomorphic(actual, target)
        
        node = find_node(graph, lambda n: n.get('slot') == 'x')
        data = { k:v for k,v in graph.nodes[node].items()
                 if k.startswith('annotation') }
        self.assertEqual(data, {
            'annotation': 'python/flowgraph/foo-slots',
            'annotation_index': 1,
            'annotation_kind': 'slot',
        })
        
        node = find_node(graph, lambda n: n.get('slot') == 'y')
        data = { k:v for k,v in graph.nodes[node].items()
                 if k.startswith('annotation') }
        self.assertEqual(data, {
            'annotation': 'python/flowgraph/foo-slots',
            'annotation_index': 2,
            'annotation_kind': 'slot',
        })
    
    def test_object_slots_primitive(self):
        """ Test that annotated object slots with primitive values are captured.
        """
        env = {}
        graph = self.record("""
            foo = objects.FooSlots()
        """, env=env)
        
        actual = graph
        target = new_flow_graph()
        outputs = target.graph['output_node']
        target.add_node('1', qual_name='FooSlots')
        target.add_node('x', slot='x')
        target.add_node('y', slot='y')
        target.add_node('sum', slot='do_sum')
        target.add_edge('1', 'x', id=self.id('foo'),
                        sourceport='__return__', targetport='self')
        target.add_edge('1', 'y', id=self.id('foo'),
                        sourceport='__return__', targetport='self')
        target.add_edge('1', 'sum', id=self.id('foo'),
                        sourceport='__return__', targetport='self')
        target.add_edge('1', outputs, id=self.id('foo'), sourceport='__return__')
        self.assert_isomorphic(actual, target)
        
        node = find_node(graph, lambda n: n.get('slot') == 'do_sum')
        ports = graph.nodes[node]['ports']
        self.assertEqual(ports, OrderedDict([
            ('self', {
                'portkind': 'input',
                'module': 'flowgraph.core.tests.objects',
                'qual_name': 'FooSlots',
                'annotation': 'python/flowgraph/foo-slots',
                'annotation_index': 1,
                'id': self.id('foo'),
            }),
            ('__return__', {
                'portkind': 'output',
                'annotation': 'python/builtins/int',
                'annotation_index': 1,
                'value': env['foo'].do_sum(),
            })
        ]))
    
    def test_object_slots_trackable(self):
        """ Test that annotated object slots with trackable values are captured.
        """
        env = {}
        actual = self.record("""
            container = objects.FooContainer()
        """, env=env)
        env['foo'] = env['container'].foo
        
        target = new_flow_graph()
        outputs = target.graph['output_node']
        target.add_node('1', qual_name='FooContainer')
        target.add_node('foo', slot='foo')
        target.add_edge('1', 'foo', id=self.id('container'),
                        sourceport='__return__', targetport='self')
        target.add_edge('foo', outputs, id=self.id('foo'), sourceport='__return__')
        target.add_edge('1', outputs, id=self.id('container'), sourceport='__return__')
        self.assert_isomorphic(actual, target)
    
    def test_two_join_three_object_flow(self):
        """ Test join of simple, three-object flow captured in two stages.
        """
        full = self.record("""
            foo = objects.Foo()
            bar = objects.bar_from_foo(foo)
            baz = objects.baz_from_bar(bar)
        """)
        env = {}
        first = self.record("""
            foo = objects.Foo()
        """, env=env)
        second = self.record("""
            bar = objects.bar_from_foo(foo)
            baz = objects.baz_from_bar(bar)
        """, env=env)
        
        joined = join(first, second)
        self.assert_isomorphic(joined, full, check_id=False)
    
    def test_three_join_three_object_flow(self):
        """ Test join of simple, three-object flow captured in three stages.
        """
        full = self.record("""
            foo = objects.Foo()
            bar = objects.bar_from_foo(foo)
            baz = objects.baz_from_bar(bar)
        """)
        env = {}
        first = self.record("""
            foo = objects.Foo()
        """, env=env)
        second = self.record("""
            bar = objects.bar_from_foo(foo)
        """, env=env)
        third = self.record("""
            baz = objects.baz_from_bar(bar)
        """, env=env)
        
        joined = join(join(first, second), third)
        self.assert_isomorphic(joined, full, check_id=False)
        
        joined = join(first, join(second, third))
        self.assert_isomorphic(joined, full, check_id=False)
    
    def test_two_join_mutation(self):
        """ Test join of two-object flow with mutation of the first object.
        """
        full = self.record("""
            foo = objects.Foo()
            bar = objects.bar_from_foo_mutating(foo)
        """)
        env = {}
        first = self.record("""
            foo = objects.Foo()
        """, env=env)
        second = self.record("""
            bar = objects.bar_from_foo_mutating(foo)
        """, env=env)
    
        joined = join(first, second)
        self.assert_isomorphic(joined, full, check_id=False)
    
    def test_graphml_serialization(self):
        """ Can a flow graph be roundtripped through GraphML?
        """
        graph = self.record("""
            foo = objects.Foo()
            bar = objects.bar_from_foo(foo)
        """)
        
        xml = write_graphml_str(flow_graph_to_graphml(graph))
        recovered = flow_graph_from_graphml(read_graphml_str(xml, multigraph=True))
        self.assertEqual(graph.graph, recovered.graph)
        self.assertEqual(graph.nodes, recovered.nodes)
        self.assertEqual(graph.edges, recovered.edges)
    
    def test_graphml_input_ports(self):
        """ Does a GraphML serialized flow graph have correct input ports?
        """
        env = {
            'foo1': objects.Foo(),
            'foo2': objects.Foo(),
        }
        recorded_graph = self.record("""
            bar1 = objects.bar_from_foo(foo1)
            bar2a = objects.bar_from_foo(foo2)
            bar2b = objects.bar_from_foo(foo2)
        """, env=env)

        outer = flow_graph_to_graphml(recorded_graph)
        root = list(outer.nodes)[0]
        graph, ports = outer.nodes[root]['graph'], outer.nodes[root]['ports']
        in_ports = [ port for port in ports.values()
                     if port['portkind'] == 'input' ]
        inputs = sorted(data['id'] for _, _, data in
                         graph.out_edges(graph.graph['input_node'], data=True))
        self.assertEqual(in_ports, [
            {
                'portkind': 'input',
                'annotation': 'python/flowgraph/foo',
            },
            {
                'portkind': 'input',
                'annotation': 'python/flowgraph/foo',
            },
        ])
        self.assertEqual(inputs, sorted([
            self.id('foo1'), self.id('foo2'), self.id('foo2')
        ]))
    
    def test_graphml_output_ports(self):
        """ Does a GraphML-serialized flow graph have correct output ports?
        """
        recorded_graph = self.record("""
            foo = objects.Foo()
            bar = objects.bar_from_foo(foo)
        """)
        
        outer = flow_graph_to_graphml(recorded_graph)
        root = list(outer.nodes)[0]
        graph, ports = outer.nodes[root]['graph'], outer.nodes[root]['ports']
        # FIXME: Outputs ports should have a deterministic order.
        sorted_ports = sorted(ports.values(),
                              key=lambda d: d['annotation'], reverse=True)
        outputs = sorted(data['id'] for _, _, data in
                         graph.in_edges(graph.graph['output_node'], data=True))
        self.assertEqual(sorted_ports, [
            {
                'portkind': 'output',
                'annotation': 'python/flowgraph/foo',
            },
            {
                'portkind': 'output',
                'annotation': 'python/flowgraph/bar',
            },
        ])
        self.assertEqual(outputs, sorted([ self.id('foo'), self.id('bar') ]))
        
        outer = flow_graph_to_graphml(recorded_graph, simplify_outputs=True)
        root = list(outer.nodes)[0]
        graph, ports = outer.nodes[root]['graph'], outer.nodes[root]['ports']
        outputs = sorted(data['id'] for _, _, data in
                         graph.in_edges(graph.graph['output_node'], data=True))
        self.assertEqual(list(ports.values()), [
            {
                'portkind': 'output',
                'annotation': 'python/flowgraph/bar',
            },
        ])
        self.assertEqual(outputs, [ self.id('bar') ])


if __name__ == '__main__':
    unittest.main()
