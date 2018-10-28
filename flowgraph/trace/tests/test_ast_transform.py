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

import ast
from textwrap import dedent
import unittest

from astor import to_source

from ..ast_transform import AttributesToFunctions, OperatorsToFunctions


class TestASTTransform(unittest.TestCase):
    """ Test cases for abstract syntax tree (AST) transformers.
    """
    
    def test_simple_getattr(self):
        """ Can we replace a simple attribute access with `getattr`?
        """
        node = ast.parse(dedent("""
            x = obj.x
            y = obj.y
        """))
        AttributesToFunctions().visit(node)
        self.assertEqual(to_source(node), dedent("""\
            x = getattr(obj, 'x')
            y = getattr(obj, 'y')
        """))
    
    def test_compound_getattr(self):
        """ Can we replace a compound attribute access with `getattr`s?
        """
        node = ast.parse('x = container.obj.x')
        AttributesToFunctions().visit(node)
        self.assertEqual(to_source(node), dedent("""\
            x = getattr(getattr(container, 'obj'), 'x')
        """))
    
    def test_simple_setattr(self):
        """ Can we replace a simple attribute assignment with `setattr`?
        """
        node = ast.parse(dedent("""
            foo.x = 10
            foo.y = 100
        """))
        AttributesToFunctions().visit(node)
        self.assertEqual(to_source(node), dedent("""\
            setattr(foo, 'x', 10)
            setattr(foo, 'y', 100)
        """))
    
    def test_compound_setattr(self):
        """ Can we replace a compound attribute asssignment with `getattr` and
        `setattr`?
        """
        node = ast.parse('container.foo.x = 10')
        AttributesToFunctions().visit(node)
        self.assertEqual(to_source(node), dedent("""\
            setattr(getattr(container, 'foo'), 'x', 10)
        """))
    
    def test_simple_delattr(self):
        """ Can we replace a simple attribute deletion with `delattr`?
        """
        node = ast.parse('del foo.x')
        AttributesToFunctions().visit(node)
        self.assertEqual(to_source(node), dedent("""\
            delattr(foo, 'x')
        """))
    
    def test_multiple_delattr(self):
        """ Can we replace a multiple deletion of attributes with `delattr`s?
        """
        node = ast.parse('del foo.x, other, foo.y')
        AttributesToFunctions().visit(node)
        self.assertEqual(to_source(node), dedent("""\
            delattr(foo, 'x')
            del other
            delattr(foo, 'y')
        """))
    
    def test_unary_op(self):
        """ Can we replace unary operators with function calls?
        """
        node = ast.parse('-x')
        OperatorsToFunctions().visit(node)
        self.assertEqual(to_source(node).strip(), 'operator.neg(x)')

        node = ast.parse('~x')
        OperatorsToFunctions().visit(node)
        self.assertEqual(to_source(node).strip(), 'operator.invert(x)')
    
    def test_binary_op(self):
        """ Can we replace binary operators with function calls?
        """
        node = ast.parse('x+y')
        OperatorsToFunctions().visit(node)
        self.assertEqual(to_source(node).strip(), 'operator.add(x, y)')

        node = ast.parse('x*y')
        OperatorsToFunctions().visit(node)
        self.assertEqual(to_source(node).strip(), 'operator.mul(x, y)')


if __name__ == '__main__':
    unittest.main()
