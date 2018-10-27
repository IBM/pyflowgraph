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

""" Abstract syntax tree (AST) transformers to supplement call tracing.

The general idea is to homogenize the rather large and complicated Python
languages by reducing special language syntax (attributes, unary and binary
operators, indexing, etc) to function calls.
"""
from __future__ import absolute_import

import ast
import six


class AttributesToFunctions(ast.NodeTransformer):
    """ Replace attribute getters/setters with function calls.

    Namely, the functions `getattr`, `setattr`, and `delattr`.
    """
    
    def visit_Attribute(self, node):
        """ Convert attribute access to `getattr` call.
        """
        self.generic_visit(node)
        if isinstance(node.ctx, ast.Load):
            args = [ node.value, ast.Str(node.attr) ]
            return to_call(to_name('getattr'), args)
        return node
    
    def visit_Assign(self, node):
        """ Convert assignment to attributes to `setattr` call.
        """
        self.generic_visit(node)
        if len(node.targets) > 1:
            # Multiple assignment not implemented.
            return node
        
        target = node.targets[0]
        if isinstance(target, ast.Name):
            return node
        elif isinstance(target, ast.Attribute):
            args = [ target.value, ast.Str(target.attr), node.value ]
            return ast.Expr(to_call(to_name('setattr'), args))

        # Destructuring assignment not implemented.
        return node
        
    def visit_Delete(self, node):
        """ Convert `del` on attributes to `delattr` call.
        """
        self.generic_visit(node)
        stmts = []
        for target in node.targets:
            if isinstance(target, ast.Attribute):
                args = [ target.value, ast.Str(target.attr) ]
                stmts.append(ast.Expr(to_call(to_name('delattr'), args)))
            else:
                stmts.append(ast.Delete([target]))
        return stmts


class OperatorsToFunctions(ast.NodeTransformer):
    """ Replace unary, binary, and other operators with function calls.
    """

    def __init__(self, operator_module=None):
        super(OperatorsToFunctions, self).__init__()
        self.operator = to_name(operator_module or 'operator')


# Helper functions

def to_call(func, args=[], keywords=[], **kwargs):
    """ Create Call AST node.
    """
    return ast.Call(func=func, args=args, keywords=[], **kwargs)

def to_name(str_or_name, ctx=None):
    """ Cast a string to a Name AST node. 
    """
    ctx = ctx or ast.Load()
    if isinstance(str_or_name, six.string_types):
        id = str_or_name
    elif isinstance(str_or_name, ast.Name):
        id = str_or_name.id
    else:
        raise TypeError("Argument must be a string or a Name AST node")
    return ast.Name(id, ctx)
