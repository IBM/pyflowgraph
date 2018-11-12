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
import fractions
import unittest

from ..inspect_function import bind_arguments


class TestInspectFunctions(unittest.TestCase):
    """ Test cases for introspection on functions.
    """
    
    def test_bind_function(self):
        """ Can we bind arguments to an ordinary function?
        """
        args = bind_arguments(fractions.gcd, 4, 10)
        self.assertEqual(args, OrderedDict([('a',4), ('b',10)]))
    
    def test_bind_constructor(self):
        """ Can we bind arguments to an object constructor?
        """
        args = bind_arguments(fractions.Fraction, 1, 2)
        self.assertEqual(args, OrderedDict([('numerator',1), ('denominator',2)]))
    
    def test_bind_method(self):
        """ Can we bind arguments to an instance method?
        """
        f = fractions.Fraction(3, 7)
        args = bind_arguments(f.limit_denominator, 2)
        self.assertEqual(args, OrderedDict([('self',f), ('max_denominator',2)]))
    
    def test_bind_builtin_function(self):
        """ Can we bind arguments to a builtin function?
        """
        args = bind_arguments(range, 10)
        self.assertEqual(args, OrderedDict([('0',10)]))
    
    def test_bind_builtin_method(self):
        """ Can we bind arguments to a builtin method?
        """
        x = [1,2,3]
        args = bind_arguments(x.append, 4)
        self.assertEqual(args, OrderedDict([('0',x), ('1',4)]))


if __name__ == '__main__':
    unittest.main()
