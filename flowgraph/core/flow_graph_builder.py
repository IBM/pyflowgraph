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

from collections import deque, OrderedDict
from copy import deepcopy
import types
from weakref import WeakKeyDictionary

from ipykernel.jsonutil import json_clean
import networkx as nx
from traitlets import HasTraits, Bool, Dict, Instance, Unicode, default

from flowgraph.kernel.slots import get_slot
from flowgraph.trace import operator as extra_operator
from flowgraph.trace.inspect_name import get_class_module_name, \
    get_class_qual_name
from flowgraph.trace.object_tracker import ObjectTracker
from flowgraph.trace.trace_event import TraceEvent, TraceCall, TraceReturn
from .annotator import Annotator
from .flow_graph import new_flow_graph


class FlowGraphBuilder(HasTraits):
    """ Build an object flow graph from a stream of trace events.
    
    A flow graph is a directed acyclic multigraph that describes the flow of
    objects through a program. Its nodes are function calls and its edges
    are (pointers to) objects. The incoming edges of a node are arguments to
    the function and outgoing edges are arguments or return values.
    (If the function is pure, the outgoing edges are only return values.)
    """
    
    # Annotator for Python objects and functions.
    annotator = Instance(Annotator, args=())

    # Tracks objects using weak references.
    object_tracker = Instance(ObjectTracker, args=())
    
    # Whether to store annotated slots for objects on creation or mutation.
    store_slots = Bool(True)
    
    # Private traits.
    _node_names = Dict()
    _stack = Instance(deque, ()) # List(Instance(_CallContext))
    
    # Public interface
    
    def __init__(self, **traits):
        super(FlowGraphBuilder, self).__init__(**traits)
        self.reset()
    
    @property
    def graph(self):
        """ Top-level flow graph.
        """
        # Make a shallow copy.
        return nx.MultiDiGraph(self._stack[0].graph)
    
    def push_event(self, event):
        """ Push a new TraceEvent to the builder.
        """
        if isinstance(event, TraceCall):
            self._push_call_event(event)
        elif isinstance(event, TraceReturn):
            self._push_return_event(event)
        else:
            raise TypeError("Event must be TraceCall or TraceReturn")
    
    def reset(self):
        """ Reset the flow graph builder.
        """
        # The bottom of the call stack does not correspond to a call event.
        # It simply contains the root flow graph and associated state.
        graph = new_flow_graph()
        self._node_names = {}
        self._stack.clear()
        self._stack.append(_CallContext(graph=graph))
    
    def is_primitive(self, obj):
        """ Is the object considered primitive?
        
        Only primitive objects will be captured as "value" data for object slots
        and function inputs and outputs. (This does not preclude getting "id"
        data if object is also weak-referenceable.)
        
        Almost always, scalar types (bool, int, float, string, etc.) should be
        considered primitive. The default implementation allows any object which
        is JSON-able (essentially, the scalar types plus the built-in container
        types if their contents are JSON-able).
        
        Note: any objects stored as "value" data will be deep-copied.
        """
        try:
            json_clean(obj)
        except ValueError:
            return False
        return True
    
    def is_pure(self, event, annotation, arg_name):
        """ Is the call event pure with respect to the given argument?
        
        In a pure functional language (like Haskell) or a language with
        copy-on-modify semantics (like R), this would always be True, but in
        Python functions frequently mutate their arguments. Nevertheless,
        we regard the function as pure unless explicitly annotated otherwise.
        
        Of course, this convention is not really "correct", but the alternative
        is flow graphs with too many false positive mutations. In addition,
        even if we assumed mutating semantics by default, we don't have the
        complicated machinery to track downstream objects that may modify the
        original object, as in the following example:
        
            df = pandas.DataFrame(...)
            x = df.values
            x[:,0] = ...    # Also a mutation of `df`
        
        In view of these difficulties, we are basically punting on tracking
        object mutations. In the future we could consider adding
        object-specific heuristics to detect mutations, e.g., for data frames
        check the column names and dtypes or even, if the data is small enough,
        a hash of the underlying data.
        """
        # Special case: important functions knowns to be impure.
        if event.qual_name in ('setattr', 'setitem') and \
                arg_name in ('obj', '0'):
            return False
        
        # Default: pure unless explicitly annotated otherwise!
        outputs = annotation.get('outputs', [])
        slots = _IOSlots(event)
        return not any(arg_name == slots._name(obj['slot']) for obj in outputs)
    
    # Protected interface
            
    def _push_call_event(self, event):
        """ Push a call event onto the stack.
        """
        # Get graph from context of previous call.
        context = self._stack[-1]
        graph = context.graph
        
        # Create a new node for this call.
        annotation = self.annotator.notate_function(event.function) or {}
        node = self._add_call_node(event, annotation)
        
        # Add edges for function arguments.
        for arg_name in event.arguments.keys():
            self._add_call_in_edge(event, node, arg_name)
        
        # If the call is not atomic, we will enter a new scope.
        # Create a nested flow graph for the node.
        nested = None
        if not event.atomic:
            nested = new_flow_graph()
            graph.nodes[node]['graph'] = nested
    
        # Push call context onto stack.
        self._stack.append(_CallContext(event=event, node=node, graph=nested))
        
    def _push_return_event(self, event):
        """ Push a return event and pop the corresponding call from the stack.
        """
        # Pop matching call event from stack to retrieve node.
        context = self._stack.pop()
        if not context.event.full_name == event.full_name:
            # Sanity check
            raise RuntimeError("Mismatched trace events")
        node = context.node

        # Get graph containing this node from context of previous call.
        context = self._stack[-1]
        graph = context.graph

        # Special case: If attribute is a bound method, remove the call node.
        # Method objects are not tracked and the method will be traced when it
        # is called, so the `getattr` node is redundant.
        return_value = event.value
        method_types = (types.MethodType, types.BuiltinMethodType)
        if event.function is getattr and isinstance(return_value, method_types):
            graph.remove_node(node)
            return
        
        # Set output for return value(s).
        if isinstance(return_value, tuple):
            # Interpret tuples as multiple return values, per Python convention.
            for i, value in enumerate(return_value):
                value_id = self.object_tracker.maybe_track(value)
                if value_id:
                    self._set_object_output_node(
                        event, value, value_id, node, '__return__.%i' % i)
        else:
            # All other objects are treated as a single return value.
            return_id = self.object_tracker.maybe_track(return_value)
            if return_id:
                self._set_object_output_node(
                    event, return_value, return_id, node, '__return__')
        
        # Set outputs for mutated arguments.
        annotation = self.annotator.notate_function(event.function) or {}
        for arg_name, arg in event.arguments.items():
            arg_id = self.object_tracker.get_id(arg)
            if arg_id and not self.is_pure(event, annotation, arg_name):
                port = self._mutated_port_name(arg_name)
                self._set_object_output_node(event, arg, arg_id, node, port)
        
        # Update event table with node.
        context.event_table[event] = (node, '__return__')
        
        # Update node and port data for this call.
        self._update_call_node_for_return(event, annotation, node)
        
    def _add_call_node(self, event, annotation):
        """ Add a new call node for a call event.
        """
        context = self._stack[-1]
        graph = context.graph
        node = self._node_name(event.qual_name)
        data = {
            'module': event.module_name,
            'qual_name': event.qual_name,
            'ports': self._get_ports_data(
                event,
                event.arguments.keys(),
                [ dom['slot'] for dom in annotation.get('inputs', []) ],
                { 'portkind': 'input' },
            ),
        }
        if annotation:
            data.update({
                'annotation': self._annotation_key(annotation),
                'annotation_kind': 'function',
            })
        graph.add_node(node, **data)
        return node
    
    def _update_call_node_for_return(self, event, annotation, node):
        """ Update node and port data of call node for a return event.
        """
        context = self._stack[-1]
        graph = context.graph
        data = graph.nodes[node]
        
        # Handle special methods (unless overriden by annotation).
        if not annotation:
            if event.function is getattr:
                # Record the attribute access as a slot.
                self._update_getattr_node_for_return(event, node)
            elif isinstance(event.function, type):
                # Record the object initializer as a constructor.
                self._update_constructor_node_for_return(event, node)
        
        # Add output ports.
        port_names = []
        return_value = event.value
        if isinstance(return_value, tuple) and \
                event.function not in (getattr, extra_operator.__tuple__):
            port_names.extend([ '__return__.%i' % i
                                for i in range(len(return_value)) ])
        elif return_value is not None:
            port_names.append('__return__')
        for arg_name in event.arguments.keys():
            if not self.is_pure(event, annotation, arg_name):
                port_names.append((arg_name, self._mutated_port_name(arg_name)))
        
        ports = data['ports']
        ports.update(self._get_ports_data(
            event,
            port_names,
            [ dom['slot'] for dom in annotation.get('outputs', []) ],
            { 'portkind': 'output' },
        ))
        
        return True

    def _update_getattr_node_for_return(self, event, node):
        """ Update a `getattr` call node for a return event.
        """
        context = self._stack[-1]
        data = context.graph.nodes[node]
        
        args = list(event.arguments.values())
        obj, name = args[0], args[1]
        note = self.annotator.notate_object(obj) or {}
        for slot_index, slot_def in enumerate(note.get('slots', [])):
            slot = slot_def['slot']
            if slot == name:
                data.update({
                    'slot': slot,
                    'annotation': self._annotation_key(note),
                    'annotation_index': slot_index+1,
                    'annotation_kind': 'slot',
                })
                break
        else:
            data['slot'] = name
    
    def _update_constructor_node_for_return(self, event, node):
        """ Update an object constructor call node for a return event.
        """
        context = self._stack[-1]
        data = context.graph.nodes[node]
        note = self.annotator.notate_object(event.value)
        if note:
            data.update({
                'annotation': self._annotation_key(note),
                'annotation_kind': 'construct',
            })
        else:
            data['construct'] = True
    
    def _add_call_in_edge(self, event, node, arg_name):
        """ Add an incoming edge to a call node.
        """
        # Track argument, if possible.
        context = self._stack[-1]
        arg = event.arguments[arg_name]
        arg_id = self.object_tracker.maybe_track(arg)

        # Get source node and port corresponding to argument, if possible.
        arg_event = event.argument_events.get(arg_name)
        if arg_id:
            # First, check if argument object is tracked.
            src, src_port = self._get_object_output_node(arg_id)
        elif arg_event and arg_event in context.event_table:
            # If that fails, fall back to static analysis, via the event table.
            src, src_port = context.event_table[arg_event]
        else:
            src, src_port = None, None
        
        # Add edge if the argument has a known output node.
        if src is not None:
            self._add_object_edge(arg, src, node, obj_id=arg_id,
                                  sourceport=src_port, targetport=arg_name)
        
        # Otherwise, mark a tracked argument as an unknown input.
        elif arg_id:
            self._add_object_input_node(arg, arg_id, node, arg_name)
    
    def _add_object_edge(self, obj, source, target, 
                         obj_id=None, sourceport=None, targetport=None):
        """ Add an edge corresponding to an object.
        """
        context = self._stack[-1]
        graph = context.graph
        data = {}
        if obj_id is not None:
            data['id'] = obj_id
        if sourceport is not None:
            data['sourceport'] = sourceport
        if targetport is not None:
            data['targetport'] = targetport
        note = self.annotator.notate_object(obj)
        if note:
            data['annotation'] = self._annotation_key(note)
        graph.add_edge(source, target, **data)
    
    def _add_object_input_node(self, obj, obj_id, node, port):
        """ Add an object as an unknown input to a node.
        """
        context = self._stack[-1]
        graph = context.graph
        input_node = graph.graph['input_node']
        self._add_object_edge(obj, input_node, node, obj_id=obj_id,
                              targetport=port)
    
    def _get_object_output_node(self, obj_id):
        """ Get the node/port of which the object is an output, if any. 
        
        An object is an "output" of a call node if it is the last node to have
        created/mutated the object.
        """
        context = self._stack[-1]
        output_table = context.output_table
        return output_table.get(obj_id, (None, None))
    
    def _set_object_output_node(self, event, obj, obj_id, node, port):
        """ Set an object as an output of a node.
        """
        context = self._stack[-1]
        graph, output_table = context.graph, context.output_table
        output_node = graph.graph['output_node']
        
        # Remove old output, if any.
        if obj_id in output_table:
            old, _ = output_table[obj_id]
            edge_data = graph.get_edge_data(old, output_node)
            keys = [ key for key, data in edge_data.items()
                     if data['id'] == obj_id ]
            assert len(keys) == 1
            graph.remove_edge(old, output_node, key=keys[0])
        
        # Set new output.
        output_table[obj_id] = (node, port)
        self._add_object_edge(obj, node, output_node, obj_id=obj_id,
                              sourceport=port)
        
        # The object has been created or mutated, so fetch its slots.
        if self.store_slots:
            self._add_object_slots(event, obj, obj_id, node, port)
    
    def _add_object_slots(self, event, obj, obj_id, node, port):
        """ Add nodes and edges for annotated slots of an object.
        """
        context = self._stack[-1]
        graph = context.graph
        note = self.annotator.notate_object(obj) or {}
        for slot_index, slot_def in enumerate(note.get('slots', [])):
            slot = slot_def['slot']
            try:
                slot_value = get_slot(obj, slot)
            except AttributeError:
                continue
            slot_node = self._node_name('slot:' + str(slot))
            slot_node_data = {
                'slot': slot,
                'annotation': self._annotation_key(note),
                'annotation_index': slot_index+1,
                'annotation_kind': 'slot',
                'ports': OrderedDict([
                    ('self', self._get_port_data(event, obj,
                        portkind='input',
                        annotation_index=1,
                    )),
                    ('__return__', self._get_port_data(event, slot_value,
                        portkind='output',
                        annotation_index=1,
                    )),
                ])
            }
            graph.add_node(slot_node, **slot_node_data)
            self._add_object_edge(obj, node, slot_node, obj_id=obj_id,
                                  sourceport=port, targetport='self')
            
            # If object is trackable, recursively set it as output.
            slot_id = self.object_tracker.maybe_track(slot_value)
            if slot_id:
                self._set_object_output_node(
                    event, slot_value, slot_id, slot_node, '__return__')
    
    def _get_ports_data(self, event, names, annotation=[], extra_data={}):
        """ Get data for the ports (input or output) of a node.
        """
        ports = OrderedDict()
        slots = _IOSlots(event)
        annotation_table = { 
            # Index annotations start at 1: it is language-agnostic.
            slots._name(slot): i+1 for i, slot in enumerate(annotation)
        }
        for name in names:
            name, portname = name if isinstance(name, tuple) else (name, name)
            try:
                obj = get_slot(slots, name)
            except AttributeError:
                obj = None
            
            data = self._get_port_data(event, obj, argname=name, **extra_data)
            if name in annotation_table:
                data['annotation_index'] = annotation_table[name]
            ports[portname] = data
        return ports
    
    def _get_port_data(self, event, obj, **extra_data):
        """ Get data for a single port on a node.
        """
        data = extra_data
        if obj is None:
            return data
        
        # Add object ID if available.
        obj_id = self.object_tracker.get_id(obj)
        if obj_id is not None:
            data['id'] = obj_id
        
        # Add value if the object is primitive.
        if self.is_primitive(obj):
            data['value'] = deepcopy(obj)
        
        # Add type information if type is not built-in.
        obj_type = obj.__class__
        module_name = get_class_module_name(obj_type)
        if not module_name == 'builtins':
            data['module'] = module_name
            data['qual_name'] = get_class_qual_name(obj_type)

        # Add object annotation, if it exists.
        note = self.annotator.notate_object(obj)
        if note:
            data['annotation'] = self._annotation_key(note)
        
        return data
    
    def _annotation_key(self, note):
        """ Get a key identifying an annotation.
        """
        keys = ('language', 'package', 'id')
        return '/'.join(note[key] for key in keys)
    
    def _node_name(self, base):
        """ Get node name unique within flow graph, including nested graphs.

        The node names are deterministic across runs.
        """
        count = self._node_names.get(base, 0) + 1
        self._node_names[base] = count
        return base + ":" + str(count)
    
    def _mutated_port_name(self, arg_name):
        """ Get name of output port for a mutated argument.
        
        Because the GraphML protocol does not support input and output ports as
        first-class entities, the names of ports must be unique across inputs
        and outputs. Therefore, when an argument is mutated and hence appears as
        both an input and output, we must give the output port a different name.
        """
        return arg_name + '!'


class _CallContext(HasTraits):
    """ Context for a trace call event.
    
    Internal state for FlowGraphBuilder.
    """
    # The trace call event for this call stack item.
    event = Instance(TraceCall)
    
    # Name of graph node created for call, if any.
    node = Unicode()
    
    # Flow graph nested in node, if any.
    graph = Instance(nx.MultiDiGraph, allow_none=True)
    
    # Output table: mapping from object ID to (node, output port) pair.
    #
    # At any given time during execution, an object is the output of at most
    # one node, i.e., there is at most one incoming edge to the special output
    # node that carries a particular object. We maintain this mapping as an
    # auxiliary data structure called the "output table". It is logically
    # superfluous--the same information is captured by the graph topology--but
    # it improves efficiency by allowing constant-time lookup.
    output_table = Dict()

    # Event table: mapping from trace event to (node, output port) pair.
    #
    # As a complement to object tracking, which doesn't always work, we
    # maintain a correspondence between `TraceValueEvent`s and their outputs.
    # The dictionary has weak reference keys because we want to allow the trace
    # events to be garbage collected once they've passed through the system.
    event_table = Instance(WeakKeyDictionary, ())


class _IOSlots(object):
    """ Get slots of a function call or return event.
    
    Implementation detail of FlowGraphBuilder.
    """

    def __init__(self, event):
        self.__event = event
    
    def _name(self, slot):
        """ Map the function slot (integer or string) to a string name, if any.
        """
        event = self.__event
        if isinstance(slot, int):
            argument_names = list(event.arguments.keys())
            try:
                return argument_names[slot]
            except IndexError:
                return None
        return slot
    
    def __getattr__(self, name):
        event = self.__event
        if name == '__return__':
            return event.value
        try:
            return event.arguments[name]
        except KeyError:
            raise AttributeError("No function slot %r" % name)
    
    def __getitem__(self, index):
        event = self.__event
        argument_names = list(event.arguments.keys())
        return event.arguments[argument_names[index]]
