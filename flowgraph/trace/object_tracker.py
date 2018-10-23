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

import six
import types
import weakref

from traitlets import HasTraits, Dict, Int


class ObjectTracker(HasTraits):
    """ Allow object lookup by ID without creating references to the object.
    
    The IDs are strings that uniquely identify the object. Unlike the integer
    IDs returned by Python's `id` function, which can be recycled when objects
    are garbage collected, these IDs are guaranteed to be unique across the
    lifetime of the object tracker.
    """
    
    # Map: memory address -> object ID.
    _mem_map = Dict()

    # Map: object ID -> weakref.
    # We would prefer to use a `WeakValueDictionary`, but it requires its
    # contents to be hashable.
    _ref_map = Dict()

    # Running counter to generate object IDs.
    _id_count = Int()

    def get_object(self, obj_id):
        """ Look up an object by ID.
        
        Returns None if the object is not being tracked or has been garbage
        collected.
        """
        ref = self._ref_map.get(obj_id)
        return ref() if ref else None
    
    def get_id(self, obj):
        """ Get the ID of a tracked object.
        
        Returns None if the object is not tracked.
        """
        if not self.is_trackable(obj):
            return None
        return self._mem_map.get(id(obj))
    
    def is_tracked(self, obj):
        """ Is the given object currently being tracked?
        """
        if not self.is_trackable(obj):
            return False
        return id(obj) in self._mem_map
    
    @classmethod
    def is_trackable(cls, obj):
        """ Is it possible to track the given object?
        
        Most importantly, primitive scalar types are not trackable, nor are
        `tuple`, `list`, and `dict` types. The latter fact is especially
        inconvenient.
        """
        # We never track function objects, even though they are weakref-able.
        if isinstance(obj, (types.FunctionType, types.MethodType)):
            return False
        
        # FIXME: Is there another way to check if an object is weakref-able?
        try:
            weakref.ref(obj)
        except TypeError:
            return False
        return True
    
    def track(self, obj):
        """ Start tracking an object.
        
        Returns an ID for the object.
        """
        if not self.is_trackable(obj):
            raise TypeError("Cannot track object of type %r" % type(obj))
        
        # Check if object is already being tracked.
        obj_addr = id(obj)
        if obj_addr in self._mem_map:
            return self._mem_map[obj_addr]
        
        # Generate a new object ID.
        self._id_count += 1
        obj_id = str(self._id_count)
        
        def obj_gc_callback(ref):
            try:
                del self._mem_map[obj_addr]
                del self._ref_map[obj_id]
            except:
                # If the ObjectTracker has itself been garbage-collected,
                # we'll get an attribute error.
                pass
        
        self._mem_map[obj_addr] = obj_id
        self._ref_map[obj_id] = weakref.ref(obj, obj_gc_callback)
        
        return obj_id
