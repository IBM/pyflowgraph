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

""" Serialization of arbitrary Python objects to/from JSON.

FIXME: The current approach based on jsonpickle is quick and dirty.
Ultimately, we want a more space efficient and less Python-centric scheme.
"""
import jsonpickle

# Install handlers for numpy arrays.
try:
    import numpy
except ImportError:
    pass
else:
    import jsonpickle.ext.numpy
    jsonpickle.ext.numpy.register_handlers()


def object_to_json(obj):
    """ Convert an arbitrary Python object to a JSON-encodable format.
    """
    pickler = jsonpickle.pickler.Pickler(keys=True)
    return pickler.flatten(obj)

def object_from_json(json):
    """ Restore an arbitrary Python object from its JSON-encodable form.
    """
    unpickler = jsonpickle.unpickler.Unpickler(keys=True)
    return unpickler.restore(json)
