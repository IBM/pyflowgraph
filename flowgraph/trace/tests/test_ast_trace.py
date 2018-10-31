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
import six
from textwrap import dedent
import unittest

from ..ast_trace import TraceFunctionCalls


class TestASTTrace(unittest.TestCase):
    """ Test cases for abstract syntax tree (AST) tracing transformers.
    """

    def setUp(self):
        """ Reset trace state for test.
        """
        self.history = []

    def trace_function(self, f):
        """ Record function evaluation (not function call!).
        """
        self.history.append(('function', f))
        return f
    
    def trace_argument(self, arg, kw=None):
        """ Record argument evaluation.
        """
        self.history.append(('arg', (kw, arg) if kw is not None else arg))
        return arg
    
    def trace_return(self, return_value):
        """ Record function return.
        """
        self.history.append(('return', return_value))
        return return_value

    def exec_ast(self, node, env=None):
        """ Execute AST node in environment.
        """
        self.env = env = env or {}
        env.update(globals())
        env['__trace__'] = self

        ast.fix_missing_locations(node)
        import astor; print(astor.to_source(node))
        code = compile(node, filename='<ast>', mode='exec')
        exec(code, env)

        return env

    def test_trace_calls(self):
        """ Can we trace calls of Python functions?
        """
        from fractions import Fraction

        node = ast.parse(dedent("""
        from fractions import Fraction
        x = Fraction(3,7)
        y = x.limit_denominator(2)
        """))
        TraceFunctionCalls('__trace__').visit(node)

        self.exec_ast(node)
        x, y = self.env['x'], self.env['y']
        self.assertEqual(x, Fraction(3,7))
        self.assertEqual(y, Fraction(1,2))
        self.assertEqual(self.history, [
            ('function', Fraction),
            ('arg', 3),
            ('arg', 7),
            ('return', Fraction(3,7)),
            ('function', x.limit_denominator),
            ('arg', 2),
            ('return', Fraction(1,2))
        ])
    
    def test_trace_builtin_calls(self):
        """ Can we trace calls of builtin functions?
        """
        node = ast.parse('x = sum(range(5))')
        TraceFunctionCalls('__trace__').visit(node)
        
        self.exec_ast(node)
        self.assertEqual(self.env['x'], sum(range(5)))
        self.assertEqual(self.history, [
            ('function', sum),
            ('function', range),
            ('arg', 5),
            ('return', range(5)),
            ('arg', range(5)),
            ('return', sum(range(5))),
        ])
    
    def test_trace_keyword_arguments(self):
        """ Can we trace calls with keyword arguments?
        """
        from fractions import Fraction

        node = ast.parse(dedent("""
        from fractions import Fraction
        Fraction(numerator=3, denominator=7)
        """))
        TraceFunctionCalls('__trace__').visit(node)

        self.exec_ast(node)
        self.assertEqual(self.history, [
            ('function', Fraction),
            ('arg', ('numerator', 3)),
            ('arg', ('denominator', 7)),
            ('return', Fraction(3,7)),
        ])


if __name__ == '__main__':
    unittest.main()
