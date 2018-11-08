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
import six
from textwrap import dedent
import unittest

from flowgraph.core.tests import objects
from ..trace_event import TraceCall, TraceReturn
from ..tracer import Tracer


class TestTracer(unittest.TestCase):
    """ Test the execution tracer.
    """

    def setUp(self):
        """ Create the tracer and set a handler for trace events.
        """
        self.tracer = Tracer()        
        self.events = []
        def handler(changed):
            event = changed['new']
            if event:
                self.events.append(event)
        self.tracer.observe(handler, 'event')
    
    def trace(self, code):
        """ Trace code in environment with test objects.
        """
        env = dict(objects=objects)
        return self.tracer.trace(dedent(code), env=env)
    
    def test_basic_call(self):
        """ Are function calls traced?
        """
        env = self.trace("""
            foo = objects.Foo()
            bar = objects.bar_from_foo(foo, x=1, y=2)
        """)
        
        events = self.events
        self.assertEqual(len(events), 4)
        
        event = events[2]
        self.assertTrue(isinstance(event, TraceCall))
        self.assertTrue(event.atomic)
        self.assertEqual(event.function, objects.bar_from_foo)
        self.assertEqual(event.module_name, objects.__name__)
        self.assertEqual(event.qual_name, 'bar_from_foo')
        self.assertEqual(event.arguments, OrderedDict([
            ('foo',env['foo']), ('x',1), ('y',2)
        ]))
        
        event = events[3]
        self.assertTrue(isinstance(event, TraceReturn))
        self.assertTrue(event.atomic)
        self.assertEqual(event.function, objects.bar_from_foo)
        self.assertEqual(event.module_name, objects.__name__)
        self.assertEqual(event.qual_name, 'bar_from_foo')
    
    def test_basic_return(self):
        """ Are function returns traced?
        """
        env = self.trace("""
            foo = objects.create_foo()
        """)
        
        events = self.events
        self.assertEqual(len(events), 2)
        
        event = events[0]
        self.assertTrue(isinstance(event, TraceCall))
        self.assertTrue(event.atomic)
        self.assertEqual(event.function, objects.create_foo)
        self.assertEqual(event.module_name, objects.__name__)
        self.assertEqual(event.qual_name, 'create_foo')
        self.assertEqual(event.arguments, OrderedDict())
        
        event = events[1]
        self.assertTrue(isinstance(event, TraceReturn))
        self.assertTrue(event.atomic)
        self.assertEqual(event.function, objects.create_foo)
        self.assertEqual(event.module_name, objects.__name__)
        self.assertEqual(event.qual_name, 'create_foo')
        self.assertEqual(event.value, env['foo'])
    
    def test_atomic_nested_return(self):
        """ Test that the bodies of atomic functions are not traced.
        """
        env = self.trace("""
            foo = objects.nested_create_foo()
        """)
        
        events = self.events
        self.assertEqual(len(events), 2)
        self.assertTrue(isinstance(events[0], TraceCall))
        self.assertTrue(isinstance(events[1], TraceReturn))
        self.assertTrue(events[0].atomic)
        self.assertTrue(events[1].atomic)
        self.assertEqual(events[0].qual_name, 'nested_create_foo')
        self.assertEqual(events[1].qual_name, 'nested_create_foo')
    
    def test_atomic_higher_order_call(self):
        """ Test that a user-defined function called from within an atomic
        function is not traced.
        """
        env = self.trace("""
            foo = objects.Foo()
            foo.apply(lambda x: objects.Bar(x))
            baz = objects.baz_from_foo(foo)
        """)
        
        events = self.events
        self.assertEqual(len(events), 8)
        self.assertEqual(events[0].qual_name, 'Foo')
        self.assertEqual(events[2].qual_name, 'getattr')
        self.assertEqual(events[4].qual_name, 'Foo.apply')
        self.assertEqual(events[6].qual_name, 'baz_from_foo')
    
    def test_getattr(self):
        """ Are attribute getters traced?
        """
        env = self.trace("""
            container = objects.FooContainer()
            foo1 = container.foo_property
            foo2 = container.foo
        """)
        
        events = self.events
        self.assertEqual(len(events), 6)
        self.assertEqual(events[0].qual_name, 'FooContainer')
        self.assertEqual(events[2].qual_name, 'getattr')
        self.assertEqual(events[2].arguments, OrderedDict([
            ('0',env['container']), ('1','foo_property')
        ]))
        self.assertEqual(events[3].value, env['foo1'])
        self.assertEqual(events[4].qual_name, 'getattr')
        self.assertEqual(events[5].value, env['foo2'])
    
    def test_setattr(self):
        """ Are attribute setters traced?
        """
        env = self.trace("""
            container = objects.FooContainer()
            container.foo = objects.Foo()
        """)
        
        events = self.events
        self.assertEqual(len(events), 6)
        self.assertEqual(events[0].qual_name, 'FooContainer')
        self.assertEqual(events[2].qual_name, 'Foo')
        self.assertEqual(events[4].qual_name, 'setattr')
        self.assertEqual(events[4].arguments, OrderedDict([
            ('obj' if six.PY3 else '0', env['container']),
            ('name' if six.PY3 else '1', 'foo'),
            ('value' if six.PY3 else '2', env['container'].foo),
        ]))
    
    def test_boxed_return(self):
        """ Can the tracer pass boxed values from a function return?
        """
        env = self.trace("objects.bar_from_foo(objects.Foo())")
        
        events = self.events
        self.assertEqual(len(events), 4)
        self.assertEqual(events[2].qual_name, 'bar_from_foo')
        self.assertIsInstance(events[2].arguments['foo'], objects.Foo)

        event = events[2].argument_events['foo']
        self.assertIsInstance(event, TraceReturn)
        self.assertEqual(event.qual_name, 'Foo')
        self.assertIs(events[3].argument_events['foo'], event)


if __name__ == '__main__':
    unittest.main()
