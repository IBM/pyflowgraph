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

from .ast_util import gensym, get_single_target, set_ctx, \
    to_attribute, to_call, to_name, to_name_constant, to_list, to_tuple

is_sequence_node = lambda node: isinstance(node, (ast.List, ast.Tuple))


class EliminateMultipleTargets(ast.NodeTransformer):
    """ Eliminate statements with multiple targets.

    Converts any assignment or deletion statement with multiple targets to a
    sequences of statements which each have a single target. We are careful
    to preserve Python's evaluation order:
    https://docs.python.org/3/reference/expressions.html#evaluation-order

    This normalization is a pre-processing step. All other AST transformers in
    this module assume that assignments and deletions have multiplicity 1.
    """

    def visit_Assign(self, node):
        """ Replace multiple assignment with single assignments.
        """
        self.generic_visit(node)
        is_multiple = len(node.targets) > 1
        is_compound = any(map(is_sequence_node, node.targets))
        is_simple = not is_compound
        if is_simple and is_multiple:
            return self.visit_simple_assign(node)
        elif is_compound and (is_multiple or is_sequence_node(node.value)):
            return self.visit_compound_assign(node)
        return node
    
    def visit_simple_assign(self, node):
        """ Visit assignment node whose targets are all simple.
        """
        temp = gensym()
        temp_target = to_name(temp, ast.Store())
        stmts = [ ast.Assign([temp_target], node.value) ]
        stmts += [ ast.Assign([target], to_name(temp))
                   for target in node.targets ]
        return stmts
    
    def visit_compound_assign(self, node):
        """ Visit assignment node with at least one compound target.
        """
        # Determine number of values (arity) of compound assignment.
        nvalues = { len(target.elts) for target in node.targets 
                    if is_sequence_node(target) }
        if len(nvalues) > 1:
            # A multiple, compound assignment with different arities, e.g.,
            # `x,y = a,b,c = ...` is not a syntax error in Python, though it
            # probably should be because it's guaranteed to cause a runtime
            # error. Raise the error here, since we cannot proceed.
            raise SyntaxError("Multiple assignment with different arities")
        nvalues = nvalues.pop()

        # Assign temporary variables.
        temps = [ gensym() for i in range(nvalues) ]
        stmts = []
        if is_sequence_node(node.value) and len(node.value.elts) == nvalues:
            # Special case: RHS is sequence literal of correct length.
            for i in range(nvalues):
                temp_target = to_name(temps[i], ast.Store())
                stmts.append(ast.Assign([temp_target], node.value.elts[i]))
        else:
            # General case.
            temp_target = to_tuple(
                (to_name(temp, ast.Store()) for temp in temps), ast.Store())
            stmts.append(ast.Assign([temp_target], node.value))

        # Rewrite assignments as sequence of assignments.
        for target in reversed(node.targets):
            if is_sequence_node(target):
                stmts.extend(ast.Assign([target.elts[i]], to_name(temps[i]))
                             for i in range(nvalues))
            else:
                temp_tuple = to_tuple(to_name(temp) for temp in temps)
                stmts.append(ast.Assign([target], temp_tuple))
                        
        return stmts

    def visit_Delete(self, node):
        """ Replace multiple deletion with single deletions.
        """
        self.generic_visit(node)
        if len(node.targets) > 1:
            return [ ast.Delete([node.target]) for target in node.targets ]
        return node


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
        target = get_single_target(node)
        if isinstance(target, ast.Attribute):
            args = [ target.value, ast.Str(target.attr), node.value ]
            return ast.Expr(to_call(to_name('setattr'), args))
        return node
    
    def visit_Delete(self, node):
        """ Convert `del` on attributes to `delattr` call.
        """
        self.generic_visit(node)
        target = get_single_target(node)
        if isinstance(target, ast.Attribute):
            args = [ target.value, ast.Str(target.attr) ]
            return ast.Expr(to_call(to_name('delattr'), args))
        return node


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
        target = get_single_target(node)
        if isinstance(target, ast.Subscript):
            fun = to_attribute(self.operator, 'setitem')
            args = [target.value, self.index_to_expr(target.slice), node.value]
            return ast.Expr(to_call(fun, args))
        return node
    
    def visit_Delete(self, node):
        """ Convert indexed `del` operation to `delitem` call.
        """
        self.generic_visit(node)
        target = get_single_target(node)
        if isinstance(target, ast.Subscript):
            fun = to_attribute(self.operator, 'delitem')
            args = [ target.value, self.index_to_expr(target.slice) ]
            return ast.Expr(to_call(fun, args))
        return node
    
    def visit_AugAssign(self, node):
        """ Convert indexed augmented assignment to `getitem`/`setitem` calls.

        Example: `x[0] += 1` -> `setitem(x, 0, iadd(getitem(x, 0), 1)))`
        """
        self.generic_visit(node)
        stmts = []
        target = node.target
        if not isinstance(target, ast.Subscript):
            return node

        # AST node for target value, gensym-ed if necessary.
        if isinstance(target.value, ast.Name):
            target_node = target.value
        else:
            target_node = to_name(gensym())
            stmts.append(ast.Assign(
                [set_ctx(target_node, ast.Store())], target.value))
        
        # AST node for index.
        # FIXME: Need to gensym the slice expression in some cases.
        index_node = self.index_to_expr(target.slice)
        
        # Main AST node for the indexed augemented assignment.
        stmts.append(ast.Expr(
            to_call(to_attribute(self.operator, 'setitem'), [
                target_node,
                index_node,
                to_call(self.op_to_function(node.op), [
                    to_call(to_attribute(self.operator, 'getitem'), [
                        target_node,
                        index_node,
                    ]),
                    node.value
                ])
            ])
        ))

        return stmts


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
            raise NotImplementedError("Multiple comparisons not supported")

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


class ContainerLiteralsToFunctions(ast.NodeTransformer):
    """ Replace container literals with function calls.
    """

    def __init__(self, operator_module=None):
        super(ContainerLiteralsToFunctions, self).__init__()
        self.operator = to_name(operator_module or 'operator')
    
    def visit_List(self, node):
        """ Convert list literal to function call.
        """
        self.generic_visit(node)
        if isinstance(node.ctx, ast.Load):
            return to_call(to_attribute(self.operator, '__list__'), node.elts)
        return node
    
    def visit_Tuple(self, node):
        """ Convert tuple literal to function call.
        """
        self.generic_visit(node)
        if isinstance(node.ctx, ast.Load):
            return to_call(to_attribute(self.operator, '__tuple__'), node.elts)
        return node
    
    def visit_Set(self, node):
        """ Convert set literal to function call.
        """
        self.generic_visit(node)
        return to_call(to_attribute(self.operator, '__set__'), node.elts)
    
    def visit_Dict(self, node):
        """ Convert dictionary literal to function call, if possible.
        """
        self.generic_visit(node)
        if all(isinstance(key, ast.Str) for key in node.keys):
            keywords = [ ast.keyword(arg=key.s, value=value)
                         for key, value in zip(node.keys, node.values) ]
            return to_call(to_name('dict'), keywords=keywords)
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