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

import inspect
from operator import attrgetter
import six

from cachetools import cachedmethod
from cachetools.keys import hashkey
from traitlets import HasTraits, Dict, Instance

from .annotation_db import AnnotationDB
from .remote_annotation_db import RemoteAnnotationDB
from ..trace.inspect_names import get_class_module_name, \
    get_class_full_name, get_func_full_name


class Annotator(HasTraits):
    """ Look up annotations for Python objects and functions.
    
    This class provides Python-specific functionality on top of the annotation
    database:
        - Type resolution based on Python's MRO (method resolution order)
        - Aggressive caching to improve performance when tracing
    """
    
    # Database of annotations.
    # Do not manually load package annotations, as the annotator will load them
    # on-the-fly as needed.
    db = Instance(AnnotationDB, args=())
    
    # Private traits.
    _func_cache = Dict()
    _type_cache = Dict()
    
    def notate_function(self, func):
        """ Find annotation for a Python function.

        By a "function", we actually mean any callable object
        (function, instance method, class method, type, etc.).
        """
        if not callable(func):
            raise TypeError("Attempt to annotate non-callable as function")
        
        pk = self._cached_notate_function(func)
        return self.db.get({'pk': pk}) if pk else None          
    
    def notate_object(self, obj):
        """ Find annotation for a Python object.
        
        The lookup is based on the object's type (see `notate_type`).
        """
        return self.notate_type(obj.__class__)
    
    def notate_type(self, type):
        """ Find annotation for a Python type.
        
        Returns a JSON dict or None if there are no annotations.
        """
        pk = self._cached_notate_type(type)
        return self.db.get({'pk': pk}) if pk else None
    
    # Private interface
    
    @cachedmethod(cache=attrgetter('_func_cache'),
                  key=lambda self, func: self._get_func_key(func))
    def _cached_notate_function(self, func):
        """ Notate a function object, returning the primary key or None.
        """        
        # If the function is a method, try to find a method annotation.
        note = None
        if inspect.ismethod(func):
            cls = self._get_method_self(func)
            query_extra = { 
                'kind': 'function',
                'method': func.__name__,
            }
            note = self._resolve_type(cls, query_extra)
        
        # Failing that, look for a function annotation.
        if note is None:
            name = get_func_full_name(func)
            package = name.split('.')[0]
            query = { 
                'language': 'python',
                'package': package,
                'kind': 'function',
                'function': name,
            }
            note = next(self._query(query), None)
        
        return note['pk'] if note else None
    
    @cachedmethod(cache=attrgetter('_type_cache'),
                  key=lambda self, type: self._get_type_key(type))
    def _cached_notate_type(self, type):
        """ Notate a type, returning the primary key or None.
        """
        extra_query = { 'kind': 'type' }
        note = self._resolve_type(type, extra_query)
        return note['pk'] if note else None
    
    def _query(self, query):
        """ Query the annotation DB.
        """
        # Ensure package annotations have been loaded.
        if isinstance(self.db, RemoteAnnotationDB):
            self.db.load_package(query['package'])
        
        return self.db.filter(query)
    
    def _resolve_type(self, type, query_extra={}):
        """ Find the best annotation for a Python type from a list of
        annotations, where "best" is defined by the partial order below.
        
        If there is no maximal element, an arbitrary element is returned.
        """
        # Get all subclasses using the MRO (we ignore the order here).
        mro = inspect.getmro(type)
        subclasses = { get_class_full_name(c) : c for c in mro }
        
        # Find the best (highest precedence) annotation.
        best = None
        for name, subclass in subclasses.items():
            package = get_class_module_name(subclass).split('.')[0]
            query = {
                'language': 'python',
                'package': package,
            }
            query.update(query_extra)
            for note in self._query(query):
                note_classes = self._get_annotation_classes(note)
                if (set(note_classes).issubset(subclasses) and
                    (best is None or 
                     self._annotation_le(subclasses, best, note))):
                    best = note
        return best
    
    def _annotation_le(self, subclasses, first, second):
        """ Is the first object annotation "less than or equal to"
        (lower precedence than) the second?
        
        We declare that `first <= second` iff every class in `first` is
        a superclass of some class in `second`. This defines a *partial order*
        on the annotations.
        """
        def issuperclass(c1, c2):
            return issubclass(subclasses[c2], subclasses[c1])
        
        first = self._get_annotation_classes(first)
        second = self._get_annotation_classes(second)
        return all(any(issuperclass(c1,c2) for c2 in second) for c1 in first)
    
    def _get_annotation_classes(self, note):
        """ Get the list of classes for an object or method annotation.
        """
        try:
            names = note['class']
        except KeyError:
            return []
        if isinstance(names, six.string_types):
            names = [ names ]
        return names
    
    def _get_func_key(self, func):
        """ Key for function cache.
        """
        # For methods, we include the type of the object to which the method
        # is bound. This will differ from the type in the method's qualified
        # name when there is subclassing without method overriding.
        if inspect.ismethod(func):
            type_key = self._get_type_key(self._get_method_self(func))
        else:
            type_key = None
        return (get_func_full_name(func), type_key)
    
    def _get_type_key(self, type):
        """ Key for type cache.
        """
        return get_class_full_name(type)
    
    def _get_method_self(self, func):
        """ Get the object to which the method is bound.
        """
        assert inspect.ismethod(func)
        if type(func.__self__) is type(object):
            # Class method: __self__ has type `type`
            cls = func.__self__
        else:
            # Instance method
            cls = func.__self__.__class__
        return cls
