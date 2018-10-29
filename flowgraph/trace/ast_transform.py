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
            raise NotImplementedError("Multiple assignment not implemented")
        
        target = node.targets[0]
        if isinstance(target, ast.Attribute):
            args = [ target.value, ast.Str(target.attr), node.value ]
            return ast.Expr(to_call(to_name('setattr'), args))
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


class IndexingToFunctions(ast.NodeTransformer):
    """ Replace indexing operations with function calls.
    """

    def __init__(self, operator_module=None):
        super(IndexingToFunctions, self).__init__()
        self.operator = to_name(operator_module or 'operator')
    
    def index_to_expr(self, index):
        """ Convert index (slice) to functional expression.
        """
        if isinstance(index, ast.Index):
            return index.value
        elif isinstance(index, ast.Slice):
            if index.lower is None and index.step is None:
                args = [ index.upper ]
            elif index.step is None:
                args = [ index.lower, index.upper ]
            else:
                args = [ index.lower, index.upper, index.step ]
            args = [ ast.NameConstant(None) if arg is None else arg
                     for arg in args ]
            return to_call(to_name('slice'), args)
        elif isinstance(index, ast.ExtSlice):
            indexes = list(map(self.index_to_expr, index.dims))
            return ast.Tuple(elts=indexes, ctx=ast.Load())
        else:
            raise TypeError("Not an index: %s" % index)
    
    def visit_Subscript(self, node):
        """ Convert indexing to `getitem` call.
        """
        self.generic_visit(node)
        if isinstance(node.ctx, ast.Load):
            args = [ node.value, self.index_to_expr(node.slice) ]
            return to_call(to_attribute(self.operator, 'getitem'), args)
        return node
    
    def visit_Assign(self, node):
        """ Convert indexed assignment to `setitem` call.
        """
        self.generic_visit(node)
        if len(node.targets) > 1:
            raise NotImplementedError("Multiple assignment not implemented")
        
        target = node.targets[0]
        if isinstance(target, ast.Subscript):
            fun = to_attribute(self.operator, 'setitem')
            args = [target.value, self.index_to_expr(target.slice), node.value]
            return ast.Expr(to_call(fun, args))
        return node
    
    def visit_Delete(self, node):
        """ Convert indexed `del` operation to `delitem` call.
        """
        self.generic_visit(node)
        stmts = []
        for target in node.targets:
            if isinstance(target, ast.Subscript):
                fun = to_attribute(self.operator, 'delitem')
                args = [ target.value, self.index_to_expr(target.slice) ]
                stmts.append(ast.Expr(to_call(fun, args)))
            else:
                stmts.append(ast.Delete([target]))
        return stmts


class OperatorsToFunctions(ast.NodeTransformer):
    """ Replace unary, binary, and other operators with function calls.
    """

    def __init__(self, operator_module=None):
        super(OperatorsToFunctions, self).__init__()
        self.operator = to_name(operator_module or 'operator')
    
    def op_to_function(self, op):
        """ Convert AST operator to function in operator module.
        """
        name = op.__class__.__name__.lower()
        name = operator_table.get(name, name)
        return to_attribute(self.operator, name)
    
    def visit_UnaryOp(self, node):
        self.generic_visit(node)
        return to_call(self.op_to_function(node.op), [node.operand])
    
    def visit_BinOp(self, node):
        self.generic_visit(node)
        return to_call(self.op_to_function(node.op), [node.left, node.right])


# Helper functions

def to_call(func, args=[], keywords=[], **kwargs):
    """ Create a Call AST node.
    """
    return ast.Call(func=func, args=args, keywords=[], **kwargs)

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

# Operator table: map AST operator name -> function name in operator module
# For whatever reason, the names are mostly but not quite consistent.

operator_table = {
    'not': 'not_',
    'uadd': 'pos',
    'usub': 'neg',
    'bitand': 'and_',
    'bitor': 'or_',
    'bitxor': 'xor',
    'div': 'truediv' if six.PY3 else 'div',
    'mult': 'mul',
    'matmult': 'matmul',
}