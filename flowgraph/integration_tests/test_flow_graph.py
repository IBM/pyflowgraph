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

import os
from pathlib2 import Path
import six
import unittest

import networkx as nx
import networkx.algorithms.isomorphism as iso

from ..core.flow_graph import new_flow_graph, flow_graph_to_graphml
from ..core.flow_graph_builder import FlowGraphBuilder
from ..core.graphml import write_graphml
from ..core.record import record_script
from ..core.remote_annotation_db import RemoteAnnotationDB
from ..trace.tracer import Tracer

data_path = Path(__file__).parent.joinpath('data')


class IntegrationTestFlowGraph(unittest.TestCase):
    """ Integration tests for Python flow graphs.
    
    Uses real Python libraries (pandas, sklearn, etc) and their annotations.
    """
    
    @classmethod
    def setUpClass(cls):
        """ Set up the annotation database.
        """
        cls.db = RemoteAnnotationDB.from_library_config()
    
    def assert_isomorphic(self, actual, target):
        """ Assert that two flow graphs are isomorphic.
        """
        node_attrs = [ 'annotation', 'qual_name', 'slot' ]
        node_defaults = [ None ] * len(node_attrs)
        edge_attrs = [ 'annotation', 'sourceport', 'targetport' ]
        edge_defaults = [ None ] * len(edge_attrs)
        node_match = iso.categorical_node_match(node_attrs, node_defaults)
        edge_match = iso.categorical_multiedge_match(edge_attrs, edge_defaults)
        matcher = iso.DiGraphMatcher(
            target, actual, node_match=node_match, edge_match=edge_match)
        self.assertTrue(matcher.is_isomorphic())
        return matcher.mapping
    
    def assert_valid_ports(self, graph):
        """ Assert that edges in flow graph have valid source and target ports.

        Downstream tools expect this consistency condition to hold.
        """
        input_node = graph.graph['input_node']
        output_node = graph.graph['output_node']
        for src, tgt, data in graph.edges(data=True):
            if src != input_node:
                src_port = data['sourceport']
                ports = graph.node[src]['ports']
                self.assertIn(src_port, ports)
                self.assertEqual(ports[src_port]['portkind'], 'output')
            if tgt != output_node:
                tgt_port = data['targetport']
                ports = graph.node[tgt]['ports']
                self.assertIn(tgt_port, ports)
                self.assertEqual(ports[tgt_port]['portkind'], 'input')
    
    def record_script(self, name, env=None, save=True):
        """ Execute and record a test script.
        """
        # Record the script.
        filename = str(data_path.joinpath(name + '.py'))
        graph = record_script(filename, env=env, cwd=str(data_path), db=self.db,
                              store_slots=False)
        
        # Save the graph as GraphML for consumption by downstream tests.
        if save:
            outname = str(data_path.joinpath(name + '.xml'))
            graphml = flow_graph_to_graphml(graph, outputs='simplify')
            write_graphml(graphml, outname)
        
        # Check consistency of node ports with edge source and target ports.
        self.assert_valid_ports(graph)
        
        return graph
    
    def test_numpy_meshgrid(self):
        """ Create two-dimensional grid using NumPy's `meshgrid`.
        """
        graph = self.record_script("numpy_meshgrid")
        target = new_flow_graph()
        outputs = target.graph['output_node']
        target.add_node('lin1', qual_name='linspace')
        target.add_node('lin2', qual_name='linspace')
        target.add_node('meshgrid', qual_name='meshgrid')
        target.add_edge('lin1', 'meshgrid', sourceport='return', targetport='0',
                        annotation='python/numpy/ndarray')
        target.add_edge('lin2', 'meshgrid', sourceport='return', targetport='1',
                        annotation='python/numpy/ndarray')
        target.add_edge('lin1', outputs, sourceport='return',
                        annotation='python/numpy/ndarray')
        target.add_edge('lin2', outputs, sourceport='return',
                        annotation='python/numpy/ndarray')
        target.add_edge('meshgrid', outputs, sourceport='return.0',
                        annotation='python/numpy/ndarray')
        target.add_edge('meshgrid', outputs, sourceport='return.1',
                        annotation='python/numpy/ndarray')
        self.assert_isomorphic(graph, target)
    
    def test_numpy_reshape(self):
        """ Reshape a NumPy array.
        """
        graph = self.record_script("numpy_reshape_array")
        graph.remove_node(graph.graph['output_node'])

        target = new_flow_graph()
        target.remove_node(target.graph['output_node'])
        target.add_node('rand', qual_name='RandomState.rand')
        target.add_node('arange', qual_name='arange')
        target.add_node('shape', qual_name='getattr', slot='shape',
                        annotation='python/numpy/ndarray')
        target.add_node('reshape', qual_name='ndarray.reshape')
        target.add_edge('rand', 'shape', sourceport='return', targetport='0',
                        annotation='python/numpy/ndarray')
        target.add_edge('arange', 'reshape', sourceport='return', targetport='self',
                        annotation='python/numpy/ndarray')
        target.add_edge('shape', 'reshape', sourceport='return', targetport='1')
        self.assert_isomorphic(graph, target)
    
    def test_numpy_slice(self):
        """ Extended slice of NumPy array.
        """
        graph = self.record_script("numpy_slice_array")
        graph.remove_node(graph.graph['output_node'])
        
        target = new_flow_graph()
        target.remove_node(target.graph['output_node'])
        target.add_node('rand', qual_name='RandomState.rand')
        target.add_node('slice', qual_name='slice')
        target.add_node('extslice', qual_name='__tuple__')
        target.add_node('getitem', qual_name='getitem')
        target.add_node('gt', qual_name='gt')
        target.add_edge('rand', 'getitem', sourceport='return', targetport='a',
                        annotation='python/numpy/ndarray')
        target.add_edge('slice', 'extslice', sourceport='return', targetport='0')
        target.add_edge('extslice', 'getitem', sourceport='return', targetport='b')
        target.add_edge('getitem', 'gt', sourceport='return', targetport='a',
                        annotation='python/numpy/ndarray')
        self.assert_isomorphic(graph, target)
    
    def test_numpy_ufunc(self):
        """ Calling a NumPy universal function ("ufunc").
        """
        graph = self.record_script("numpy_ufunc")
        graph.remove_node(graph.graph['output_node'])
        
        target = new_flow_graph()
        target.remove_node(target.graph['output_node'])
        target.add_node('pi', qual_name='getattr', slot='pi')
        target.add_node('mul', qual_name='mul')
        target.add_node('linspace', qual_name='linspace')
        target.add_node('sin', qual_name='sin')
        target.add_edge('pi', 'mul', sourceport='return', targetport='b',
                        annotation='python/builtins/float')
        target.add_edge('mul', 'linspace', sourceport='return', targetport='stop',
                        annotation='python/builtins/float')
        target.add_edge('linspace', 'sin', sourceport='return', targetport='0',
                        annotation='python/numpy/ndarray')
        self.assert_isomorphic(graph, target)
    
    def test_pandas_read_sql(self):
        """ Read SQL table using pandas and SQLAlchemy.
        """
        graph = self.record_script("pandas_read_sql")
        target = new_flow_graph()
        outputs = target.graph['output_node']
        target.add_node('create_engine', qual_name='create_engine')
        target.add_node('read_table', qual_name='read_sql_table',
                        annotation='python/pandas/read-sql-table')
        target.add_edge('create_engine', 'read_table',
                        sourceport='return', targetport='con',
                        annotation='python/sqlalchemy/engine')
        target.add_edge('create_engine', outputs, sourceport='return',
                        annotation='python/sqlalchemy/engine')
        target.add_edge('read_table', outputs, sourceport='return',
                        annotation='python/pandas/data-frame')
        self.assert_isomorphic(graph, target)
    
    def test_scipy_clustering_kmeans(self):
        """ K-means clustering on the Iris data using NumPy and SciPy.
        """
        graph = self.record_script("scipy_clustering_kmeans")
        graph.remove_node(graph.graph['output_node'])

        target = new_flow_graph()
        target.remove_node(target.graph['output_node'])
        target.add_node('read', qual_name='genfromtxt',
                        annotation='python/numpy/genfromtxt')
        target.add_node('delete', qual_name='delete')
        target.add_node('kmeans', qual_name='kmeans2',
                        annotation='python/scipy/kmeans2')
        target.add_edge('read', 'delete', annotation='python/numpy/ndarray',
                        sourceport='return', targetport='arr')
        target.add_edge('delete', 'kmeans', annotation='python/numpy/ndarray',
                        sourceport='return', targetport='data')
        self.assert_isomorphic(graph, target)
    
    @unittest.skipUnless(six.PY3, "pd.read_csv needs Py2-compatible annotation")
    def test_sklearn_clustering_kmeans(self):
        """ K-means clustering on the Iris dataset using sklearn.
        """
        graph = self.record_script("sklearn_clustering_kmeans")
        graph.remove_node(graph.graph['output_node'])
        
        target = new_flow_graph()
        target.remove_node(target.graph['output_node'])
        target.add_node('read', qual_name='_make_parser_function.<locals>.parser_f',
                        annotation='python/pandas/read-table')
        target.add_node('drop', qual_name='DataFrame.drop')
        target.add_node('values', qual_name='getattr', slot='values')
        target.add_edge('read', 'drop', annotation='python/pandas/data-frame',
                        sourceport='return', targetport='self')
        target.add_edge('drop', 'values', annotation='python/pandas/data-frame',
                        sourceport='return', targetport='0')
        target.add_node('kmeans', qual_name='KMeans',
                        annotation='python/sklearn/k-means')
        target.add_node('fit', qual_name='KMeans.fit',
                        annotation='python/sklearn/fit')
        target.add_node('clusters', qual_name='getattr', slot='labels_',
                        annotation='python/sklearn/k-means')
        target.add_edge('kmeans', 'fit', annotation='python/sklearn/k-means',
                        sourceport='return', targetport='self')
        target.add_edge('values', 'fit', annotation='python/numpy/ndarray',
                        sourceport='return', targetport='X')
        target.add_edge('fit', 'clusters', annotation='python/sklearn/k-means',
                        sourceport='self!', targetport='0')
        self.assert_isomorphic(graph, target)
    
    def test_sklearn_clustering_metric(self):
        """ Compare sklearn clustering models using a cluster similarity metric.
        """
        graph = self.record_script("sklearn_clustering_metrics")
        graph.remove_node(graph.graph['output_node'])
        
        target = new_flow_graph()
        target.remove_node(target.graph['output_node'])
        target.add_node('make_blobs', qual_name='make_blobs')
        target.add_node('kmeans', qual_name='KMeans',
                        annotation='python/sklearn/k-means')
        target.add_node('fit_kmeans', qual_name='KMeans.fit_predict',
                        annotation='python/sklearn/fit-predict-clustering')
        target.add_node('agglom', qual_name='AgglomerativeClustering',
                        annotation='python/sklearn/agglomerative')
        target.add_node('fit_agglom',
                        qual_name=('ClusterMixin' if six.PY3 else
                            'AgglomerativeClustering') + '.fit_predict',
                        annotation='python/sklearn/fit-predict-clustering')
        target.add_node('score', qual_name='mutual_info_score')
        target.add_edge('kmeans', 'fit_kmeans',
                        sourceport='return', targetport='self',
                        annotation='python/sklearn/k-means')
        target.add_edge('make_blobs', 'fit_kmeans',
                        sourceport='return.0', targetport='X',
                        annotation='python/numpy/ndarray')
        target.add_edge('agglom', 'fit_agglom',
                        sourceport='return', targetport='self',
                        annotation='python/sklearn/agglomerative')
        target.add_edge('make_blobs', 'fit_agglom',
                        sourceport='return.0', targetport='X',
                        annotation='python/numpy/ndarray')
        target.add_edge('fit_kmeans', 'score',
                        sourceport='return', targetport='labels_true',
                        annotation='python/numpy/ndarray')
        target.add_edge('fit_agglom', 'score',
                        sourceport='return', targetport='labels_pred',
                        annotation='python/numpy/ndarray')
        self.assert_isomorphic(graph, target)
    
    @unittest.skipUnless(six.PY3, "pd.read_csv needs Py2-compatible annotation")
    def test_sklearn_regression_metrics(self):
        """ Errors metrics for linear regression using sklearn.
        """
        graph = self.record_script("sklearn_regression_metrics")
        graph.remove_node(graph.graph['output_node'])
        
        target = new_flow_graph()
        target.remove_node(target.graph['output_node'])
        target.add_node('read', qual_name='_make_parser_function.<locals>.parser_f',
                        annotation='python/pandas/read-table')
        target.add_node('X', qual_name='DataFrame.drop')
        target.add_node('y', qual_name='getitem')
        target.add_node('lm', qual_name='LinearRegression',
                        annotation='python/sklearn/linear-regression')
        target.add_node('fit', qual_name='LinearRegression.fit',
                        annotation='python/sklearn/fit-regression')
        target.add_node('predict', qual_name='LinearModel.predict',
                        annotation='python/sklearn/predict-regression')
        target.add_node('l1', qual_name='mean_absolute_error',
                        annotation='python/sklearn/mean-absolute-error')
        target.add_node('l2', qual_name='mean_squared_error',
                        annotation='python/sklearn/mean-squared-error')
        target.add_edge('read', 'X', sourceport='return', targetport='self',
                        annotation='python/pandas/data-frame')
        target.add_edge('read', 'y', sourceport='return', targetport='a',
                        annotation='python/pandas/data-frame')
        target.add_edge('lm', 'fit', sourceport='return', targetport='self',
                        annotation='python/sklearn/linear-regression')
        target.add_edge('X', 'fit', sourceport='return', targetport='X',
                        annotation='python/pandas/data-frame')
        target.add_edge('y', 'fit', sourceport='return', targetport='y',
                        annotation='python/pandas/series')
        target.add_edge('fit', 'predict', sourceport='self!', targetport='self',
                        annotation='python/sklearn/linear-regression')
        target.add_edge('X', 'predict', sourceport='return', targetport='X',
                        annotation='python/pandas/data-frame')
        target.add_edge('y', 'l1', sourceport='return', targetport='y_true',
                        annotation='python/pandas/series')
        target.add_edge('predict', 'l1', sourceport='return', targetport='y_pred',
                        annotation='python/numpy/ndarray')
        target.add_edge('y', 'l2', sourceport='return', targetport='y_true',
                        annotation='python/pandas/series')
        target.add_edge('predict', 'l2', sourceport='return', targetport='y_pred',
                        annotation='python/numpy/ndarray')
        self.assert_isomorphic(graph, target)
    
    @unittest.skipIf('CI' in os.environ, "needs to download R dataset")
    def test_statsmodel_regression(self):
        """ Linear regression on an R dataset using statsmodels.
        """
        graph = self.record_script("statsmodels_regression")
        target = new_flow_graph()
        outputs = target.graph['output_node']
        target.add_node('read', qual_name='get_rdataset',
                        annotation='python/statsmodels/get-r-dataset')
        target.add_node('read-get', qual_name='getattr', slot='data',
                        annotation='python/statsmodels/dataset')
        target.add_node('ols',
                        qual_name=('Model' if six.PY3 else 'OLS') + '.from_formula',
                        annotation='python/statsmodels/ols-from-formula')
        target.add_node('fit',
                        qual_name=('RegressionModel' if six.PY3 else 'OLS') + '.fit',
                        annotation='python/statsmodels/fit')
        target.add_edge('read', 'read-get',
                        sourceport='return', targetport='0',
                        annotation='python/statsmodels/dataset')
        target.add_edge('read-get', 'ols',
                        sourceport='return', targetport='data',
                        annotation='python/pandas/data-frame')
        target.add_edge('ols', 'fit',
                        sourceport='return', targetport='self',
                        annotation='python/statsmodels/ols')
        target.add_edge('read', outputs, sourceport='return',
                        annotation='python/statsmodels/dataset')
        target.add_edge('read-get', outputs, sourceport='return',
                        annotation='python/pandas/data-frame')
        target.add_edge('ols', outputs, sourceport='return',
                        annotation='python/statsmodels/ols')
        target.add_edge('fit', outputs, sourceport='return',
                        annotation='python/statsmodels/regression-results-wrapper')
        self.assert_isomorphic(graph, target)


if __name__ == '__main__':
    unittest.main()
