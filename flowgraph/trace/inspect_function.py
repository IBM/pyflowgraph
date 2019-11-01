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

""" Introspection on functions.
"""
from __future__ import absolute_import

from collections import OrderedDict
import inspect
import string
import sys
try:
    # Python 3.3+
    from inspect import signature
except ImportError:
    # Python 2.7 to 3.2
    from funcsigs import signature

# As of Python 3.6, **kwargs is finally guaranteed to be ordered.
# https://www.python.org/dev/peps/pep-0468/
kwargs_ordered = sys.version_info >= (3, 6)


def bind_arguments(fun, *args, **kwargs):
    """ Bind arguments to function or method.

    Returns an ordered dictionary mapping argument names to values. Unlike
    `inspect.signature`, the `self` parameter of bound instance methods is
    included as an argument.
    """
    arguments = OrderedDict()

    # If the callable is an instance method, bind the `self` argument.
    if is_instance_method(fun):
        arguments['self'] = fun.__self__

    # Bind all other arguments, preferably using `inspect.signature`.
    try:
        sig = signature(fun)
    except ValueError:
        # `inspect.signature()` doesn't work on builtins.
        # https://stackoverflow.com/q/42134927
        arguments.update(_bind_arguments_without_signature(args, kwargs,
            arg_name=_fallback_argument_namer(fun)))
    else:
        arguments.update(_bind_arguments_with_signature(sig, args, kwargs))

    return arguments


def _bind_arguments_with_signature(sig, args, kwargs={}):
    """ Bind function arguments using a `Signature` object.
    """
    bound = sig.bind(*args, **kwargs)
    arguments = bound.arguments

    # Expand variable arguments (*args) and variable keywords (**kwargs).
    for param in sig.parameters.values():
        if param.kind == param.VAR_POSITIONAL:
            try:
                args = arguments.pop(param.name)
            except KeyError: pass
            else:
                arguments.update(_bind_arguments_without_signature(args))
        elif param.kind == param.VAR_KEYWORD:
            try:
                kwargs = arguments.pop(param.name)
            except KeyError: pass
            else:
                if not kwargs_ordered:
                    kwargs = OrderedDict((k, kwargs[k])
                                         for k in sorted(kwargs.keys()))
                arguments.update(kwargs)

    return arguments


def _bind_arguments_without_signature(args, kwargs={}, arg_name=str):
    """ Bind function arguments in the absence of a signature.

    Useful for builtin functions, whose signatures cannot be inspected.
    """
    arguments = OrderedDict()
    for i, value in enumerate(args):
        arguments[arg_name(i)] = value
    arguments.update(kwargs)
    return arguments


def _fallback_argument_namer(fun):
    if getattr(fun, '__module__', None) in ('operator', '_operator'):
        # Not strictly necessary but ensures consistency between Python 3.7+
        # and earlier versions of Python, which makes testing more convenient.
        return lambda i: string.ascii_lowercase[i]
    elif is_instance_method(fun):
        return lambda i: str(i+1)
    else:
        return str


def is_instance_method(fun):
    """ Is the callable a bound instance method?

    More reliable than `inspect.ismethod`.
    """
    fun_self = getattr(fun, '__self__', None)
    return fun_self is not None and not inspect.isclass(fun_self) and \
        not inspect.ismodule(fun_self)
