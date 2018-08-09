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

import gc
import unittest

from flowgraph.core.tests import objects
from ..object_tracker import ObjectTracker


class TestObjectTracker(unittest.TestCase):
    
    def test_is_trackable(self):
        """ Are objects correctly identified as trackable or not trackable?
        """
        is_trackable = ObjectTracker.is_trackable
        self.assertFalse(is_trackable(None))
        self.assertFalse(is_trackable(0))
        self.assertFalse(is_trackable('foo'))
        
        foo = objects.Foo()
        self.assertTrue(is_trackable(foo))
        self.assertFalse(is_trackable(foo.do_sum))

    def test_get_object(self):
        """ Can we get a tracked object by ID?
        """
        tracker = ObjectTracker()
        foo = objects.Foo()
        foo_id = tracker.track(foo)
        self.assertTrue(tracker.is_tracked(foo))
        self.assertEqual(tracker.get_object(foo_id), foo)
        
        other_id = tracker.get_id(foo)
        self.assertEqual(other_id, foo_id)
    
    def test_gc_cleanup(self):
        """ Does the tracker clean up when an object is garbage collected?
        """
        tracker = ObjectTracker()
        foo = objects.Foo()
        foo_id = tracker.track(foo)
        self.assertTrue(tracker.is_tracked(foo))
        
        del foo
        gc.collect()
        self.assertFalse(tracker.get_object(foo_id))
        

if __name__ == '__main__':
    unittest.main()
