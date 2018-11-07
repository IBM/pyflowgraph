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

from traitlets import List

from ..ast_tracer import ASTTracer, TraceFunctionCalls

# Imports for test code only.
from fractions import Fraction


class TestASTTracer(unittest.TestCase):
    """ Test cases for abstract syntax tree (AST) tracing transformers.
    """

    def setUp(self):
        """ Reset trace state for test.
        """
        self.history = []
        self.tracer = LoggingASTTracer(log=self.history)

    def exec_ast(self, node, env=None):
        """ Execute AST node in environment.
        """
        self.env = env = env or {}
        env.update(globals())
        env['__trace__'] = self.tracer

        ast.fix_missing_locations(node)
        code = compile(node, filename='<ast>', mode='exec')
        exec(code, env)

        return env

    def test_trace_calls(self):
        """ Can we trace calls of Python functions?
        """
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
            ('function', Fraction, 2),
            ('arg', 3),
            ('arg', 7),
            ('return', Fraction(3,7)),
            ('function', x.limit_denominator, 1),
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
            ('function', sum, 1),
            ('function', range, 1),
            ('arg', 5),
            ('return', range(5)),
            ('arg', range(5)),
            ('return', sum(range(5))),
        ])
    
    def test_trace_keyword_arguments(self):
        """ Can we trace calls with keyword arguments?
        """
        node = ast.parse(dedent("""
        from fractions import Fraction
        Fraction(numerator=3, denominator=7)
        """))
        TraceFunctionCalls('__trace__').visit(node)

        self.exec_ast(node)
        self.assertEqual(self.history, [
            ('function', Fraction, 2),
            ('arg', ('numerator', 3)),
            ('arg', ('denominator', 7)),
            ('return', Fraction(3,7)),
        ])

    def test_trace_star_args(self):
        """ Can we trace calls with *args?
        """
        node = ast.parse(dedent("""
        from fractions import Fraction
        args = [3, 7]
        Fraction(*args)
        """))
        TraceFunctionCalls('__trace__').visit(node)

        self.exec_ast(node)
        self.assertEqual(self.history, [
            ('function', Fraction, 1),
            ('*arg', [3, 7]),
            ('return', Fraction(3,7)),
        ])
    
    def test_trace_star_kwargs(self):
        """ Can we trace calls with **kwargs?
        """
        node = ast.parse(dedent("""
        from fractions import Fraction
        kwargs = { 'numerator': 3, 'denominator': 7}
        Fraction(**kwargs)
        """))
        TraceFunctionCalls('__trace__').visit(node)

        self.exec_ast(node)
        self.assertEqual(self.history, [
            ('function', Fraction, 1),
            ('**arg', { 'numerator': 3, 'denominator': 7 }),
            ('return', Fraction(3,7)),
        ])

    def test_trace_star_args_and_kwargs(self):
        """ Can we trace calls with both *args and **kwargs?
        """
        node = ast.parse(dedent("""
        from fractions import Fraction
        args = [3]
        kwargs = { 'denominator': 7}
        Fraction(*args, **kwargs)
        """))
        TraceFunctionCalls('__trace__').visit(node)

        self.exec_ast(node)
        self.assertEqual(self.history, [
            ('function', Fraction, 2),
            ('*arg', [3]),
            ('**arg', { 'denominator': 7 }),
            ('return', Fraction(3,7)),
        ])


class LoggingASTTracer(ASTTracer):

    log = List()

    def trace_function(self, func, nargs):
        self.log.append(('function', func, nargs))
        return func
    
    def trace_argument(self, arg_value, arg_name=None, nstars=0):
        self.log.append(
            ('*'*nstars + 'arg',
             (arg_name, arg_value) if arg_name else arg_value)
        )
        return arg_value
    
    def _trace_return(self, return_value):
        self.log.append(('return', return_value))
        return return_value


if __name__ == '__main__':
    unittest.main()
