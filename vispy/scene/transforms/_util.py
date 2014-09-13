# -*- coding: utf-8 -*-
# Copyright (c) 2014, Vispy Development Team.
# Distributed under the (new) BSD License. See LICENSE.txt for more info.

from __future__ import division

import numpy as np
from functools import wraps


def arg_to_array(func):
    """
    Decorator to convert argument to array.
    """
    def fn(self, arg, *args, **kwds):
        return func(self, np.array(arg), *args, **kwds)
    return fn


def as_vec4(obj, default=(0, 0, 0, 1)):
    """
    Convert *obj* to 4-element vector (numpy array with shape[-1] == 4)

    If *obj* has < 4 elements, then new elements are added from *default*.
    For inputs intended as a position or translation, use default=(0,0,0,1).
    For inputs intended as scale factors, use default=(1,1,1,1).
    """
    obj = np.array(obj)

    # If this is a single vector, reshape to (1, 4)
    if obj.ndim == 1:
        obj = obj[np.newaxis, :]

    # For multiple vectors, reshape to (..., 4)
    if obj.shape[-1] < 4:
        new = np.empty(obj.shape[:-1] + (4,), dtype=obj.dtype)
        new[:] = default
        new[..., :obj.shape[-1]] = obj
        obj = new
    elif obj.shape[-1] > 4:
        raise TypeError("Array shape %s cannot be converted to vec4"
                        % obj.shape)

    return obj


def arg_to_vec4(func):
    """
    Decorator for converting argument to vec4 format suitable for 4x4 matrix
    multiplication.

    [x, y]      =>  [[x, y, 0, 1]]

    [x, y, z]   =>  [[x, y, z, 1]]

    [[x1, y1],      [[x1, y1, 0, 1],
     [x2, y2],  =>   [x2, y2, 0, 1],
     [x3, y3]]       [x3, y3, 0, 1]]

    If 1D input is provided, then the return value will be flattened.
    Accepts input of any dimension, as long as shape[-1] <= 4

    Alternatively, any class may define its own transform conversion interface
    by defining a _transform_in() method that returns an array with shape
    (.., 4), and a _transform_out() method that accepts the same array shape
    and returns a new (mapped) object.

    """
    @wraps(func)
    def fn(self, arg, *args, **kwds):
        if isinstance(arg, (tuple, list, np.ndarray)):
            arg = np.array(arg)
            flatten = arg.ndim == 1
            arg = as_vec4(arg)

            ret = func(self, arg, *args, **kwds)
            if flatten and ret is not None:
                return ret.flatten()
            return ret
        elif hasattr(arg, '_transform_in'):
            arr = arg._transform_in()
            ret = func(self, arr, *args, **kwds)
            return arg._transform_out(ret)
        else:
            raise TypeError("Cannot convert argument to 4D vector: %s" % arg)
    return fn


class TransformCache(object):
    """ Utility class for managing a cache of transforms that map along an
    Entity path.

    This is an LRU cache; items are removed if they are not accessed after
    *max_age* calls to roll().

    Notes
    -----
    This class is used by SceneCanvas to ensure that ChainTransform instances
    are re-used across calls to draw_visual(). SceneCanvas creates one
    TransformCache instance for each top-level visual drawn, and calls
    roll() on each cache before drawing, which removes from the cache any
    transforms that were not accessed during the last draw cycle.
    """
    def __init__(self, max_age=1):
        self._cache = {}  # maps {key: [age, transform]}
        self.max_age = max_age

    def get(self, path):
        """ Get a transform from the cache that maps along *path*, which must
        be a list of Transforms to apply in reverse order (last transform is
        applied first).

        Accessed items have their age reset to 0.
        """
        key = tuple(map(id, path))
        item = self._cache.get(key, None)
        if item is None:
            item = [0, self._create(path)]
            self._cache[key] = item
        item[0] = 0  # reset age for this item

        # make sure the chain is up to date
        #tr = item[1]
        #for i, entity in enumerate(path[1:]):
        #    if tr.transforms[i] is not entity.transform:
        #        tr[i] = entity.transform

        return item[1]

    def _create(self, path):
        # import here to avoid import cycle
        from .chain import ChainTransform
        return ChainTransform(path)

    def roll(self):
        """ Increase the age of all items in the cache by 1. Items whose age
        is greater than self.max_age will be removed from the cache.
        """
        rem = []
        for key, item in self._cache.items():
            if item[0] > self.max_age:
                rem.append(key)
            item[0] += 1

        for key in rem:
            del self._cache[key]
