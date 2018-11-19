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

""" Inspect names of classes and functions.
"""
import sys
import types

function_types = (types.LambdaType, types.FunctionType, types.MethodType,
                  types.BuiltinFunctionType, types.BuiltinMethodType)


def get_class_module_name(typ):
    """ Get name of module in which type was defined.
    """
    return _fix_module_name(typ.__module__)

def get_class_qual_name(typ):
    """ Get qualified name of class.
    
    See PEP 3155: "Qualified name for classes and functions"
    """
    if sys.version_info >= (3, 3):
        return typ.__qualname__
    else:
        # Not possible on older versions of Python. Just give up.
        return typ.__name__

def get_class_full_name(typ):
    """ Get the full name of a class.
    """
    module_name = get_class_module_name(typ)
    qual_name = get_class_qual_name(typ)
    if module_name == 'builtins':
        return qual_name
    return module_name + '.' + qual_name


def get_func_module_name(func):
    """ Get name of module in which the function object was defined.
    """
    # Typical case: callable object with non-null `__module__` attribute.
    module_name = getattr(func, '__module__', None)
    if module_name is not None:
        return _fix_module_name(module_name)

    # Special case: non-function callable object (e.g., a `numpy.ufunc`).
    # Defer to object's class.
    if not isinstance(func, function_types):
        return get_class_module_name(func.__class__)

    # Special case: function object with null `__module__` attribute, e.g.,
    # builtin methods like `numpy.random.rand`. Defer to bound instance.
    func_self = getattr(func, '__self__', None)
    if func_self is not None:
        return get_class_module_name(func_self.__class__)


def get_func_qual_name(func):
    """ Get the qualified name of a function object.
    
    See PEP 3155: "Qualified name for classes and functions"
    """
    try:
        # Typical case for Python 3.3+.
        return func.__qualname__
    
    except AttributeError:
        # Typical case for Python 2.7. Also, for certain function-like objects
        # that do not have qual names, like numpy ufuncs:
        # https://github.com/numpy/numpy/issues/4952

        # If a class method or instance method, fish out the class manually.
        func_self = getattr(func, '__self__', None)
        if isinstance(func, function_types) and func_self is not None:
            if type(func_self) is type(object):
                # Class method
                return func_self.__name__ + '.' + func.__name__
            else:
                # Instance method
                return type(func_self).__name__ + '.' + func.__name__
    
        # Give up and return `__name__`.
        return func.__name__


def get_func_full_name(func):
    """ Get the full name of a function object.
    """
    module_name = get_func_module_name(func)
    qual_name = get_func_qual_name(func)
    if module_name == 'builtins':
        return qual_name
    return module_name + '.' + qual_name


def _fix_module_name(name):
    """ Fix up name of Python module.
    """
    # Python 2 only: use 'builtins' for consistency with Python 3.
    if name == '__builtin__':
        name = 'builtins'
    
    # Hack to replace __main__ with correct module name.
    # See PEP 451: "A ModuleSpec Type for the Import System"
    if name == '__main__':
        spec = getattr(sys.modules['__main__'], '__spec__', None)
        if spec is not None:
            name = spec.name

    return name
