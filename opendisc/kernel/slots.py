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
from six.moves import reduce
import types


def get_slots(obj, slots):
    """ Get slots on the given object.
    
    A slot is generalized attribute. See `get_slot` for details.
    """
    if isinstance(slots, dict):
        return { key: get_slots(obj, value) for key, value in slots.items() }
    elif isinstance(slots, list):
        return [ get_slots(obj, value) for value in slots ]
    elif isinstance(slots, six.integer_types + six.string_types):
        return get_slot(obj, slots)
    else:
        raise TypeError("`slots` must be dict, list, string, or integer")


def get_slot(obj, slot):
    """ Get a slot on the given object.
    
    A slot is generalized attribute ala Django's variable lookup in HTML
    templates. We support:
        - Attributes
        - Bound methods (with no arguments)
        - Dictionary lookup
        - List indexing
    
    Raises an AttributeError if the slot cannot be retrieved.
    """
    if isinstance(slot, six.string_types):
        keys = slot.split('.')
        return reduce(_get_single_slot, keys, obj)
    elif isinstance(slot, six.integer_types):
        return obj[slot]
    else:
        raise TypeError("`slot` must be string or integer")

def _get_single_slot(obj, key):
    try:
        value = getattr(obj, key)
    except AttributeError:
        try:
            key = int(key)
        except ValueError:
            pass
        try:
            return obj[key]
        except:
            raise AttributeError("Cannot retrieve slot %r" % key)
    else:
        if isinstance(value, types.MethodType):
            if not value.__self__ is obj:
                raise AttributeError(
                    "Cannot retrieve method slot %r: method not bound to object" % key)
            if six.get_function_code(value).co_argcount > 1:
                raise AttributeError(
                    "Cannot retrieve method slot %r: too many arguments" % key)
            return value()
        else:
            return value
