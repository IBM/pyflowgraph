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

from .. import operator


class TestOperators(unittest.TestCase):
    """ Test functions for replacing Python syntax.
    """
    
    def test_list(self):
        """ Test function for list literals.
        """
        self.assertEqual(operator.__list__(), [])
        self.assertEqual(operator.__list__(1), [1])
        self.assertEqual(operator.__list__(1,2,3), [1,2,3])

    def test_tuple(self):
        """ Test function for tuple literals.
        """
        self.assertEqual(operator.__tuple__(), ())
        self.assertEqual(operator.__tuple__(1), (1,))
        self.assertEqual(operator.__tuple__(1,2,3), (1,2,3))
    
    def test_set(self):
        """ Test function for set literals.
        """
        self.assertEqual(operator.__set__(), set())
        self.assertEqual(operator.__set__(1), {1})
        self.assertEqual(operator.__set__(1,2,3), {1,2,3})


if __name__ == '__main__':
    unittest.main()
