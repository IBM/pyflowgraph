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

""" Test classes and functions for the Annotator and Tracer.
"""

class Foo(object):
    
    def __init__(self, x=1, y=1):
        self.x = x
        self.y = y
    
    def apply(self, f):
        return [f(self.x), f(self.y)]
    
    def do_sum(self):
        return self.x + self.y
    
    def do_prod(self):
        return self.x * self.y


class Bar(Foo):
    
    @classmethod
    def make_bar(cls):
        return cls(x=2, y=2)

class BarMixin(object):
    pass

class BarWithMixin(Bar, BarMixin):
    pass

class Baz(Bar, BarMixin):
    pass


class FooSlots(object):
    
    def __init__(self, x=1, y=1):
        self.x = x
        self.y = y
    
    def do_sum(self):
        return self.x + self.y


class FooContainer(object):
    
    def __init__(self):
        self.foo = Foo()
    
    @property
    def foo_property(self):
        return self.foo


def create_foo():
    return Foo()

def create_foo_and_bar():
    foo = Foo()
    bar = Bar()
    return (foo, bar)

def nested_create_foo():
    foo = create_foo()
    return foo

def foo_x_sum(foos):
    return sum(foo.x for foo in foos)


def bar_from_foo(foo, x=None, y=None):
    return Bar(x if x else foo.x, y if y else foo.y)

def bar_from_foo_mutating(foo):
    foo.y = 0
    return Bar(foo.x, foo.y)
    
def baz_from_foo(foo):
    return Baz(foo.x, foo.y)

def baz_from_bar(bar):
    return Baz(bar.x, bar.y)


def sum_varargs(x, y=0, *args, **kw):
    return x + y + sum(args) + sum(kw.values())
