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

""" Utilities for working with Python abstract syntax trees (ASTs).
"""
from __future__ import absolute_import

import ast
import copy
import six
import sys


# Convenience functions for creating AST nodes

def to_call(func, args=[], keywords=[], starargs=None, kwargs=None):
    """ Create a Call AST node.
    """
    if sys.version_info.major >= 3 and sys.version_info.minor >= 5:
        # Representation of *args and **kwargs changed in Python 3.5.
        assert starargs is None and kwargs is None
        return ast.Call(func, args, keywords)
    else:
        return ast.Call(func, args, keywords, starargs, kwargs)

def to_attribute(value, attr, ctx=None):
    """ Create an Attribute AST node.
    """
    return ast.Attribute(value, attr, ctx or ast.Load())

def to_name(str_or_name, ctx=None):
    """ Cast a string to a Name AST node.
    """
    if isinstance(str_or_name, six.string_types):
        id = str_or_name
    elif isinstance(str_or_name, ast.Name):
        id = str_or_name.id
    else:
        raise TypeError("Argument must be a string or a Name AST node")
    return ast.Name(id, ctx or ast.Load())

def to_name_constant(value):
    """ Create a NameConstant AST node from a constant (True, False, None).
    """
    if sys.version_info.major >= 3 and sys.version_info.minor >= 4:
        # NameConstant AST node new in Python 3.4.
        return ast.NameConstant(value)
    else:
        return to_name(str(value))

def to_list(elts, ctx=None):
    """ Create a List AST node.
    """
    return ast.List(list(elts), ctx or ast.Load())

def to_tuple(elts, ctx=None):
    """ Create a Tuple AST node.
    """
    return ast.Tuple(list(elts), ctx or ast.Load())

def set_ctx(node, ctx=None):
    """ Replace AST context without mutation.
    """
    node = copy.copy(node)
    node.ctx = ctx or ast.Load()
    return node
