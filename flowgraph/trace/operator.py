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

""" Python syntax as functions.

Supplements the `operator` module in the Python standard library.
"""


def __list__(*args):
    """ Function for list literals.

    __list__(x, y, z, ...) == [ x, y, z, ... ]
    """
    return list(args)


def __tuple__(*args):
    """ Function for tuple literals.

    __tuple__(x, y, z, ...) == ( x, y, z, ... )
    """
    return args


def __set__(*args):
    """ Function for set literals.

    __set__(x, y, z, ...) == { x, y, z, ... }
    """
    return set(args)
