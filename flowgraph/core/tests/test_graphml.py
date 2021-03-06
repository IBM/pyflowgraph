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

import unittest
import networkx as nx

from ..graphml import read_graphml_str, write_graphml_str


def roundtrip(graph, **kwargs):
    """ Round trip a networkx graph to/from GraphML.
    """
    xml = write_graphml_str(graph, **kwargs)
    return read_graphml_str(xml)


class TestGraphMLIO(unittest.TestCase):
    """ Test reading and writing GraphML.
    """
    
    def assert_graphs_equal(self, one, two):
        """ Assert that two networkx graphs are equal.
        
        This is exact equality, including node/edge names and attributes.
        """
        # These are added by the GraphML reader, but we ignore them.
        for graph in (one, two):
            graph.graph.pop('node_default', None)
            graph.graph.pop('edge_default', None)
        
        self.assertEqual(one.graph, two.graph)
        self.assertEqual(one.nodes, two.nodes)
        self.assertEqual(one.edges, two.edges)

    def test_basic_graph(self):
        """ Can we round-trip a basic directed graph?
        """
        graph = nx.DiGraph()
        graph.graph['name'] = 'foo-graph'
        graph.add_node('foo', kind='entity')
        graph.add_edge('foo', 'bar', id=0)
        graph.add_edge('foo', 'baz', id=1)
        self.assert_graphs_equal(roundtrip(graph), graph)
    
    def test_bytes_property(self):
        """ Can we store both unicode and bytes strings?
        """
        graph = nx.Graph()
        graph.add_node('foo', val1=u'foo', val2=b'foo')
        target = nx.Graph()
        target.add_node('foo', val1='foo', val2='foo')
        self.assert_graphs_equal(roundtrip(graph), target)
        
        # Store bytes as string attribute, not JSON.
        xml = write_graphml_str(graph)
        self.assertFalse("json" in xml)
    
    def test_json_property(self):
        """ Can we store JSON objects as graph/node/edge properties?
        """
        graph = nx.DiGraph()
        graph.graph['numbers'] = {'foo': 0, 'bar': 1}
        graph.add_node('foo', value={'kind': 'entity'})
        graph.add_edge('foo', 'bar', value={'id': 0})
        graph.add_edge('foo', 'baz', value=None)
        self.assert_graphs_equal(roundtrip(graph), graph)
    
    def test_nested_graph(self):
        """ Can a node contain a nested subgraph?
        """
        graph = nx.DiGraph()
        graph.add_node('foo-container', id='fc')
        graph.add_node('bar-container', id='bc')
        graph.add_edge('foo-container', 'bar-container')
        
        foo_graph = nx.DiGraph()
        foo_graph.add_node('foo1', kind='foo')
        foo_graph.add_node('foo2', kind='foo')
        foo_graph.add_edge('foo1', 'foo2')
        graph.nodes['foo-container']['graph'] = foo_graph
        
        bar_graph = nx.DiGraph()
        bar_graph.add_node('bar1', kind='bar')
        bar_graph.add_node('bar2', kind='bar')
        bar_graph.add_edge('bar1', 'bar2')
        graph.nodes['bar-container']['graph'] = bar_graph
        
        recovered = roundtrip(graph)
        foo_recovered = recovered.nodes['foo-container']['graph']
        bar_recovered = recovered.nodes['bar-container']['graph']
        self.assert_graphs_equal(foo_recovered, foo_graph)
        self.assert_graphs_equal(bar_recovered, bar_graph)
    
    def test_nested_graph_edges_undirected(self):
        """ Can an undirected nested graph contain references to parent node?
        """
        graph = nx.Graph()
        graph.add_node('root')
        nested = nx.DiGraph(node='__node__')
        nx.add_path(nested, ['__node__', 'n1', 'n2', '__node__'])
        graph.nodes['root']['graph'] = nested

        recovered = roundtrip(graph)
        nested_recovered = recovered.nodes['root']['graph']
        self.assert_graphs_equal(nested_recovered, nested)
        
        # The reference node ID should only appear as a graph attribute.
        xml = write_graphml_str(graph)
        self.assertEqual(xml.count('__node__'), 1)
    
    def test_nested_graph_edges_directed(self):
        """ Can a directed nested graph contain references to the parent node?
        """
        graph = nx.DiGraph()
        graph.add_node('root')
        nested = nx.DiGraph(input_node='__in__', output_node='__out__')
        nx.add_path(nested, ['__in__', 'n1', 'n2', '__out__'])
        graph.nodes['root']['graph'] = nested

        recovered = roundtrip(graph)
        nested_recovered = recovered.nodes['root']['graph']
        self.assert_graphs_equal(nested_recovered, nested)
        
        # The reference node IDs should only appear as graph attributes.
        xml = write_graphml_str(graph)
        self.assertEqual(xml.count('__in__'), 1)
        self.assertEqual(xml.count('__out__'), 1)
    
    def test_duplicate_node_ids(self):
        """ Are duplicate node IDs in sibling nested graphs detected?
        """
        nested = nx.DiGraph()
        nested.add_node('dup')
        graph = nx.DiGraph()
        graph.add_node('root1', graph=nested)
        graph.add_node('root2', graph=nested)
        self.assertRaises(nx.NetworkXError, write_graphml_str, graph)
    
    def test_ports(self):
        """ Can a graph contain nodes with ports and edge between ports?
        """
        graph = nx.DiGraph()
        graph.add_node('n1', ports={
            'p1': {'kind':'foo'},
            'p2': {'kind':'bar'},
        })
        graph.add_node('n2', ports={
            'p1': {'kind':'bar'},
        })
        graph.add_edge('n1','n2', sourceport='p2', targetport='p1')
        self.assert_graphs_equal(roundtrip(graph), graph)
        
        # Check that there are actually ports in the XML!
        # (The serialization could be achieved through node and edge data.)
        xml = write_graphml_str(graph)
        self.assertTrue('<port name="p1">' in xml)
        self.assertTrue('sourceport="p2"' in xml)
        self.assertTrue('targetport="p1"' in xml)


if __name__ == '__main__':
    unittest.main()
