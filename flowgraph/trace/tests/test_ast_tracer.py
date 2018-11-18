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

from ..ast_tracer import ASTTracer, ASTTraceTransformer

# Imports for test code only.
from fractions import Fraction


class TestASTTracer(unittest.TestCase):
    """ Test cases for abstract syntax tree (AST) tracing transformers.
    """

    def setUp(self):
        """ Reset trace state for test.
        """
        self.tracer = LoggingASTTracer()
        self.call_history = self.tracer.call_history
        self.var_history = self.tracer.var_history

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
        ASTTraceTransformer('__trace__').visit(node)

        self.exec_ast(node)
        x, y = self.env['x'], self.env['y']
        self.assertEqual(x, Fraction(3,7))
        self.assertEqual(y, Fraction(1,2))
        self.assertEqual(self.call_history, [
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
        ASTTraceTransformer('__trace__').visit(node)
        
        self.exec_ast(node)
        self.assertEqual(self.env['x'], sum(range(5)))
        self.assertEqual(self.call_history, [
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
        ASTTraceTransformer('__trace__').visit(node)

        self.exec_ast(node)
        self.assertEqual(self.call_history, [
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
        ASTTraceTransformer('__trace__').visit(node)

        self.exec_ast(node)
        self.assertEqual(self.call_history, [
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
        ASTTraceTransformer('__trace__').visit(node)

        self.exec_ast(node)
        self.assertEqual(self.call_history, [
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
        ASTTraceTransformer('__trace__').visit(node)

        self.exec_ast(node)
        self.assertEqual(self.call_history, [
            ('function', Fraction, 2),
            ('*arg', [3]),
            ('**arg', { 'denominator': 7 }),
            ('return', Fraction(3,7)),
        ])
    
    def test_trace_var_access(self):
        """ Can we trace a variable access?
        """
        node = ast.parse('x')
        ASTTraceTransformer('__trace__').visit(node)

        self.exec_ast(node, env={'x': 1})
        self.assertEqual(self.var_history, [
            ('read', 'x', 1),
        ])
    
    def test_trace_var_assign(self):
        """ Can we trace a variable assignment?
        """
        node = ast.parse('x = 1')
        ASTTraceTransformer('__trace__').visit(node)

        env = self.exec_ast(node)
        self.assertEqual(self.var_history, [
            ('write', ['x'], 1),
        ])
        self.assertEqual(env['x'], 1)
    
    def test_trace_var_multiple_assign(self):
        """ Can we trace a multiple variable assignment?
        """
        node = ast.parse('x = y = 1')
        ASTTraceTransformer('__trace__').visit(node)

        env = self.exec_ast(node)
        self.assertEqual(self.var_history, [
            ('write', ['x','y'], 1),
        ])
        self.assertEqual(env['x'], 1)
        self.assertEqual(env['y'], 1)
    
    def test_trace_var_compound_assign(self):
        """ Can we trace a compound variable assignment?
        """
        node = ast.parse('x, y = (0, 1)')
        ASTTraceTransformer('__trace__').visit(node)

        env = self.exec_ast(node)
        self.assertEqual(self.var_history, [
            ('write', [('x','y')], (0,1)),
        ])
        self.assertEqual(env['x'], 0)
        self.assertEqual(env['y'], 1)
    
    def test_trace_var_delete(self):
        """ Can we trace a variable deletion?
        """
        node = ast.parse('del x')
        ASTTraceTransformer('__trace__').visit(node)
        
        env = self.exec_ast(node, env={'x': 1})
        self.assertEqual(self.var_history, [
            ('delete', ['x'])
        ])
        self.assertNotIn('x', env)
    
    def test_trace_var_multiple_delete(self):
        """ Can we trace a multiple variable deletion?
        """
        node = ast.parse('del x, y')
        ASTTraceTransformer('__trace__').visit(node)
        
        env = self.exec_ast(node, env={'x': 0, 'y': 1})
        self.assertEqual(self.var_history, [
            ('delete', ['x','y'])
        ])
        self.assertNotIn('x', env)
        self.assertNotIn('y', env)


class LoggingASTTracer(ASTTracer):

    call_history = List()
    var_history = List()

    def _trace_function(self, func, nargs):
        self.call_history.append(('function', func, nargs))
        return func
    
    def _trace_argument(self, arg_value, arg_name=None, nstars=0):
        self.call_history.append(
            ('*'*nstars + 'arg',
             (arg_name, arg_value) if arg_name else arg_value)
        )
        return arg_value
    
    def _trace_return(self, return_value, multiple_values=False):
        self.call_history.append(('return', return_value))
        return return_value
    
    def _trace_access(self, name, value):
        self.var_history.append(('read', name, value))
        return value
    
    def _trace_assign(self, names, value):
        self.var_history.append(('write', names, value))
        return value

    def _trace_delete(self, names):
        self.var_history.append(('delete', names))


if __name__ == '__main__':
    unittest.main()
