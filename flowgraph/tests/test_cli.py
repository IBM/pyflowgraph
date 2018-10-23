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

from pathlib2 import Path
import unittest

from click.testing import CliRunner

from ..core.flow_graph import flow_graph_from_graphml
from ..core.graphml import read_graphml_str
from ..cli import cli

data_path = Path(__file__).parent.joinpath('data')


class TestCLI(unittest.TestCase):
    """ Test the command-line interface to pyflowgraph.
    """
    
    def test_record_file(self):
        """ Test that a file can be recorded using the CLI.
        """
        filename = str(data_path.joinpath('sklearn_make_blobs.py'))
        runner = CliRunner(mix_stderr=False)
        result = runner.invoke(cli, [filename])
        xml = result.output
        graph = flow_graph_from_graphml(read_graphml_str(xml))
        self.assertGreater(len(graph), 0)


if __name__ == '__main__':
    unittest.main()
