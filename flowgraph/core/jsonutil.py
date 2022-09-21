""" Utilities to manipulate JSON objects.

Copied from Jupyter's `ipykernel`:
https://github.com/ipython/ipykernel/blob/main/ipykernel/jsonutil.py

Note that `json_clean` has been deprecated in jupyter-client>=7.
"""

import math
import numbers
import types
from binascii import b2a_base64
from datetime import datetime

ISO8601 = "%Y-%m-%dT%H:%M:%S.%f"


def json_clean(obj):
    """Clean an object to ensure it's safe to encode in JSON.

    Atomic, immutable objects are returned unmodified.  Sets and tuples are
    converted to lists, lists are copied and dicts are also copied.

    Note: dicts whose keys could cause collisions upon encoding (such as a dict
    with both the number 1 and the string '1' as keys) will cause a ValueError
    to be raised.

    Parameters
    ----------
    obj : any python object

    Returns
    -------
    out : object
        A version of the input which will not cause an encoding error when
        encoded as JSON.  Note that this function does not *encode* its inputs,
        it simply sanitizes it so that there will be no encoding errors later.

    """
    # types that are 'atomic' and ok in json as-is.
    atomic_ok = (str, type(None))

    # containers that we need to convert into lists
    container_to_list = (tuple, set, types.GeneratorType)

    # Since bools are a subtype of Integrals, which are a subtype of Reals,
    # we have to check them in that order.

    if isinstance(obj, bool):
        return obj

    if isinstance(obj, numbers.Integral):
        # cast int to int, in case subclasses override __str__ (e.g. boost enum, #4598)
        return int(obj)

    if isinstance(obj, numbers.Real):
        # cast out-of-range floats to their reprs
        if math.isnan(obj) or math.isinf(obj):
            return repr(obj)
        return float(obj)

    if isinstance(obj, atomic_ok):
        return obj

    if isinstance(obj, bytes):
        # unanmbiguous binary data is base64-encoded
        # (this probably should have happened upstream)
        return b2a_base64(obj).decode('ascii')

    if isinstance(obj, container_to_list) or (
        hasattr(obj, '__iter__') and hasattr(obj, '__next__')):
        obj = list(obj)

    if isinstance(obj, list):
        return [json_clean(x) for x in obj]

    if isinstance(obj, dict):
        # First, validate that the dict won't lose data in conversion due to
        # key collisions after stringification.  This can happen with keys like
        # True and 'true' or 1 and '1', which collide in JSON.
        nkeys = len(obj)
        nkeys_collapsed = len(set(map(str, obj)))
        if nkeys != nkeys_collapsed:
            raise ValueError('dict cannot be safely converted to JSON: '
                             'key collision would lead to dropped values')
        # If all OK, proceed by making the new dict that will be json-safe
        out = {}
        for k,v in obj.items():
            out[str(k)] = json_clean(v)
        return out
    if isinstance(obj, datetime):
        return obj.strftime(ISO8601)

    # we don't understand it, it's probably an unserializable object
    raise ValueError("Can't clean for JSON: %r" % obj)
