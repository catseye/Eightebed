# -*- coding: utf-8 -*-

"""
Contexts.  Can be used for type checking and other static analysis.
"""

notset = object()
isset = object()


class Context(dict):
    """
    >>> d = Context({ 'a': 2, 'b': 3 })
    >>> e = Context({ 'c': 4 }, parent=d)
    >>> e.lookup('c')
    4
    >>> e.lookup('b')
    3
    >>> e.lookup('e', None) is None
    True
    >>> e.lookup('e')
    Traceback (most recent call last):
    ...
    KeyError: 'e'
    >>> d.declare('d', 7)
    >>> e.lookup('d')
    7
    >>> d.declare('b', 4)
    Traceback (most recent call last):
    ...
    KeyError: 'b already declared'
    >>> e.declare('b', 4)
    Traceback (most recent call last):
    ...
    KeyError: 'b already declared'
    >>> e.empty()
    >>> e.lookup('c', None) is None
    True
    >>> d.lookup('a', None) is None
    True

    """

    def __init__(self, initial={}, parent=None):
        dict.__init__(self, initial)
        self.parent = parent

    def lookup(self, name, default=notset):
        if name in self:
            return self[name]
        if self.parent is None:
            if default is notset:
                raise KeyError(name)
            return default
        return self.parent.lookup(name, default=default)

    def declare(self, name, value):
        if self.lookup(name, default=isset) is not isset:
            raise KeyError("%s already declared" % name)
        self[name] = value

    def empty(self):
        self.clear()
        if self.parent is not None:
            self.parent.empty()

    def __repr__(self):
        return "Context(%s, parent=%s)" % (
            dict.__repr__(self), repr(self.parent)
        )


if __name__ == "__main__":
    import doctest
    doctest.testmod()
