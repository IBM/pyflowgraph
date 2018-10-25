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

import inspect
import unittest
import sys

from flowgraph.core.tests import objects
from ..inspect_names import *


class TestInspectNames(unittest.TestCase):
    """ Test cases for inspecting names of classes and functions.
    """
    
    def test_get_class_module_name(self):
        """ Can we get the module in which a class is defined?
        """
        module = objects.__name__
        self.assertEqual(get_class_module_name(objects.Foo), module)
    
    def test_get_class_qual_name(self):
        """ Can we get the qualified name of a class?
        """
        self.assertEqual(get_class_qual_name(Toplevel), 'Toplevel')
        if sys.version_info[0] >= 3 and sys.version_info[1] >= 3:
            self.assertEqual(get_class_qual_name(Nested.Inner), 'Nested.Inner')
    
    def test_get_class_full_name(self):
        """ Can we get the full name of a class?
        """
        full_name = objects.__name__ + '.Foo'
        self.assertEqual(get_class_full_name(objects.Foo), full_name)
        self.assertEqual(get_class_full_name(str), 'str')
    
    def test_get_func_module_name(self):
        """ Can we get the module in which a function object is defined?
        """
        module = objects.__name__
        self.assertEqual(get_func_module_name(objects.create_foo), module)
        self.assertEqual(get_func_module_name(objects.Foo.do_sum), module)
        self.assertEqual(get_func_module_name(objects.Foo().do_sum), module)
    
    def test_get_func_qual_name(self):
        """ Can we get the qualified name of a function object?
        """
        def assert_qual_name(func, name):
            self.assertEqual(get_func_qual_name(func), name)
        
        assert_qual_name(toplevel, 'toplevel')
        assert_qual_name(Toplevel().f, 'Toplevel.f')
        assert_qual_name(Toplevel.f_cls, 'Toplevel.f_cls')
        if sys.version_info[0] >= 3:
            # No Python 2 support for static methods
            assert_qual_name(Toplevel.f_static, 'Toplevel.f_static')
        assert_qual_name(lambda_f, '<lambda>')
    
    def test_get_func_full_name(self):
        """ Can we get the full name of a function object?
        """
        full_name = objects.__name__ + '.create_foo'
        self.assertEqual(get_func_full_name(objects.create_foo), full_name)
        self.assertEqual(get_class_full_name(map), 'map')


# Test data

class Toplevel(object):
    
    def f(self):
        return inspect.currentframe()
    
    @classmethod
    def f_cls(cls):
        return inspect.currentframe()
    
    @staticmethod
    def f_static():
        return inspect.currentframe()

class Nested(object):
    
    class Inner(object):
        def g(self):
            return inspect.currentframe()
    
    def __call__(self):
        return Nested.Inner()

def toplevel():
    return inspect.currentframe()

def nested():
    def inner():
        return inspect.currentframe()
    return inner

lambda_f = lambda: inspect.currentframe()


if __name__ == '__main__':
    unittest.main()
