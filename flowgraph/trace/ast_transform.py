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
import copy
import six
import sys


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
        self.op_to_function = InplaceOperatorsToFunctions(self.operator)\
            .op_to_function
    
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
            args = [ to_name_constant(None) if arg is None else arg
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
    
    def visit_AugAssign(self, node):
        """ Convert indexed augmented assignment to `getitem`/`setitem` calls.

        Example: `x[0] += 1` -> `setitem(x, 0, iadd(getitem(x, 0), 1)))`
        """
        # FIXME: Gensym the subscript value to avoid two evaluations.
        self.generic_visit(node)
        target = node.target
        if isinstance(target, ast.Subscript):
            index = self.index_to_expr(target.slice)
            return ast.Expr(to_call(to_attribute(self.operator, 'setitem'), [
                target.value,
                index,
                to_call(self.op_to_function(node.op), [
                    to_call(to_attribute(self.operator, 'getitem'), [
                        target.value,
                        index,
                    ]),
                    node.value
                ])
            ]))
        return node


class InplaceOperatorsToFunctions(ast.NodeTransformer):
    """ Replace inplace binary operators with assignment plus function call.
    """

    def __init__(self, operator_module=None):
        super(InplaceOperatorsToFunctions, self).__init__()
        self.operator = to_name(operator_module or 'operator')
    
    def op_to_function(self, op):
        """ Convert AST operator to function in operator module.
        """
        name = op.__class__.__name__.lower()
        return to_attribute(self.operator, inplace_operator_table[name])
    
    def visit_AugAssign(self, node):
        """ Convert augmented assignment to assignment plus function call.

        Example: `x += 1' -> `x = operator.iadd(x, 1)`
        """
        # FIXME: Gensym the LHS to avoid two evaluations.
        self.generic_visit(node)
        rhs = to_call(self.op_to_function(node.op),
                      [set_ctx(node.target), node.value])
        return ast.Assign([node.target], rhs)


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
        """ Convert unary operator to function call.

        Example: `-x` -> `operator.neg(x)`
        """
        self.generic_visit(node)
        if isinstance(node.operand, ast.Num):
            # Don't transform negations of numeric literals. Just treat them
            # as literals.
            return node
        return to_call(self.op_to_function(node.op), [node.operand])
    
    def visit_BinOp(self, node):
        """ Convert binary operator to function call.

        Example: `x+y` -> `operator.add(x,y)`
        """
        self.generic_visit(node)
        return to_call(self.op_to_function(node.op), [node.left, node.right])
    
    def visit_Compare(self, node):
        """ Convert comparison operator to function call.

        Example: `x<y` -> `operator.lt(x,y)`
        """
        self.generic_visit(node)
        if len(node.ops) > 1:
            raise NotImplementedError("Multiple comparisons not implemented")

        op, comparator = node.ops[0], node.comparators[0]
        if isinstance(op, ast.In):
            # Special case: `contains` reverses the operands.
            return to_call(to_attribute(self.operator, 'contains'),
                           [comparator, node.left])
        elif isinstance(op, ast.NotIn):
            # Special case: there is no `not_contains`.
            return to_call(to_attribute(self.operator, 'not_'), [
                to_call(to_attribute(self.operator, 'contains'),
                           [comparator, node.left])
            ])
        else:
            # General case
            return to_call(self.op_to_function(op), [node.left, comparator])


# Helper functions

def to_call(func, args=[], keywords=[]):
    """ Create a Call AST node.
    """
    if sys.version_info.major >= 3 and sys.version_info.minor >= 5:
        # Representation of *args and **kwargs changed in Python 3.5.
        return ast.Call(func, args, keywords)
    else:
        return ast.Call(func, args, keywords, None, None)

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

def set_ctx(node, ctx=None):
    """ Replace AST context without mutation.
    """
    node = copy.copy(node)
    node.ctx = ctx or ast.Load()
    return node


# Operator table: map AST operator name -> function name in operator module
# For whatever reason, the names are mostly but not quite consistent.

operator_table = {
    'not': 'not_',
    'uadd': 'pos',
    'usub': 'neg',
    'bitand': 'and_',
    'bitor': 'or_',
    'bitxor': 'xor',
    'mult': 'mul',
    'matmult': 'matmul',
    'div': 'truediv' if six.PY3 else 'div',
    'noteq': 'ne',
    'lte': 'le',
    'gte': 'ge',
    'is': 'is_',
    'isnot': 'is_not',
}

inplace_operator_table = {
    'add': 'iadd',
    'sub': 'isub',
    'mult': 'imul',
    'matmult': 'imatmul',
    'div': 'itruediv' if six.PY3 else 'idiv',
    'floordiv': 'ifloordiv',
    'mod': 'imod',
    'pow': 'ipow',
    'bitand': 'iand',
    'bitor': 'ior',
    'bitxor': 'ixor',
    'lshift': 'ilshift',
    'rshift': 'irshift',
}