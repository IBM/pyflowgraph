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

from astor import to_source

from ..ast_transform import make_tracing_call_wrapper, WrapCalls, \
    AttributesToFunctions


class TestASTTransform(unittest.TestCase):
    """ Test cases for abstract syntax tree (AST) transformers.
    """

    def exec_ast(self, node, env=None):
        """ Execute AST node in environment.
        """
        ast.fix_missing_locations(node)
        code = compile(node, filename='<ast>', mode='exec')
        env = env or {}
        exec(code, globals(), env)
        return env
    
    def make_history_call_wrapper(self, history):
        """ Create call wrapper that records call and return history.
        """
        def on_call(fun, arguments):
            history.append(('call', fun.__name__, list(arguments.items())))
        def on_return(fun, arguments, return_value):
            history.append(('return', fun.__name__, return_value))
        return make_tracing_call_wrapper(
            on_call=on_call, on_return=on_return)

    def test_tracing_call_wrapper(self):
        """ Can we rewrite calls in AST with pre- and post- call hooks?
        """
        from fractions import Fraction

        node = ast.parse(dedent("""
        from fractions import Fraction
        x = Fraction(3,7)
        y = x.limit_denominator(2)
        """))
        WrapCalls('__trace__').visit(node)

        history = []
        env = dict(__trace__=self.make_history_call_wrapper(history))
        self.exec_ast(node, env=env)
        self.assertEqual(env['x'], Fraction(3,7))
        self.assertEqual(env['y'], Fraction(1,2))
        self.assertEqual(history, [
            ('call', 'Fraction', [('numerator',3),('denominator',7)]),
            ('return', 'Fraction', Fraction(3,7)),
            ('call', 'limit_denominator',
             [('self',env['x']), ('max_denominator',2)]),
            ('return', 'limit_denominator', Fraction(1,2))
        ])
    
    def test_tracing_call_wrapper_builtins(self):
        """ Can we rewrite calls of builtin functions?
        """
        node = ast.parse('x = sum(range(5))')
        WrapCalls('__trace__').visit(node)
        
        history = []
        env = dict(__trace__=self.make_history_call_wrapper(history))
        self.exec_ast(node, env=env)
        self.assertEqual(env['x'], sum(range(5)))
        self.assertEqual(history, [
            ('call', 'range', [('0',5)]),
            ('return', 'range', range(5)),
            ('call', 'sum', [('iterable' if six.PY3 else '0',range(5))]),
            ('return', 'sum', sum(range(5))),
        ])
    
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


if __name__ == '__main__':
    unittest.main()
