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


def get_class_module_name(typ):
    """ Get name of module in which type was defined.
    """
    return _fix_module_name(typ.__module__)

def get_class_qual_name(typ):
    """ Get qualified name of class.
    
    See PEP 3155: "Qualified name for classes and functions"
    """
    if sys.version_info[0] >= 3 and sys.version_info[1] >= 3:
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
    return _fix_module_name(func.__module__)

def get_func_qual_name(func):
    """ Get the qualified name of a function object.
    
    See PEP 3155: "Qualified name for classes and functions"
    """
    # Python 2 implementation
    if sys.version_info[0] == 2:
        name = func.__name__
        if isinstance(func, types.MethodType):
            if type(func.im_self) is type(object):
                # Case 1: class method
                return func.im_self.__name__ + '.' + name
            else:
                # Case 2: instance method
                return func.im_class.__name__ + '.' + name
        else:
            # Case 3: ordinary function
            return name
    
    # Python 3 implementation
    elif sys.version_info[0] >= 3 and sys.version_info[1] >= 3:
        return func.__qualname__
    
    else:
        raise NotImplementedError("Only implemented for Python 2 and 3.3+")

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
