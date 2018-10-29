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

from pathlib2 import Path
import unittest

from . import objects
from ..annotator import Annotator


class TestAnnotator(unittest.TestCase):
    
    def setUp(self):
        objects_path = Path(objects.__file__).parent
        json_path = objects_path.joinpath('data', 'annotations.json')
        self.annotator = Annotator()
        self.annotator.db.load_file(json_path)
    
    def test_function(self):
        """ Can we notate a function?
        """
        note = self.annotator.notate_function(objects.create_foo)
        self.assertEqual(note['id'], 'create-foo')
        self.assertEqual(note['language'], 'python')
        self.assertEqual(note['package'], 'flowgraph')
    
    def test_method_basic(self):
        """ Can we notate a method?
        """
        note = self.annotator.notate_function(objects.Foo().do_sum)
        self.assertEqual(note['id'], 'foo-sum')
    
        note = self.annotator.notate_function(objects.Bar().do_sum)
        self.assertEqual(note['id'], 'foo-sum')
    
    def test_method_precedence(self):
        """ Can we notate a method with multiple class matches using the
        precedence rules?
        """
        note = self.annotator.notate_function(objects.Foo().do_prod)
        self.assertEqual(note['id'], 'foo-prod')
    
        note = self.annotator.notate_function(objects.Bar().do_prod)
        self.assertEqual(note['id'], 'bar-prod')
    
    def test_object_basic(self):
        """ Can we notate an object from its class?
        """
        note = self.annotator.notate_object(objects.Foo())
        self.assertEqual(note['id'], 'foo')
        self.assertEqual(note['language'], 'python')
        self.assertEqual(note['package'], 'flowgraph')
        
        note = self.annotator.notate_type(objects.Foo)
        self.assertEqual(note['id'], 'foo')
        
        note = self.annotator.notate_object(0)
        self.assertEqual(note['id'], 'int')
        self.assertEqual(self.annotator.notate_object(None), None)
    
    def test_object_constructor(self):
        """ Can we annotate an object constructor as a function?
        """
        note = self.annotator.notate_function(objects.Empty)
        self.assertEqual(note['id'], 'new-empty')
    
    def test_object_precedence(self):
        """ Can we notate an object with mulitple class matches using the
        precedence rules?
        """
        note = self.annotator.notate_type(objects.Bar)
        self.assertEqual(note['id'], 'bar')
        
        note = self.annotator.notate_type(objects.BarWithMixin)
        self.assertEqual(note['id'], 'bar-with-mixin')
        
        note = self.annotator.notate_type(objects.Baz)
        self.assertEqual(note['id'], 'baz')


if __name__ == '__main__':
    unittest.main()
