# -*- coding: utf-8 -*-

"""
Rooibos, a parser combinator module for Python.

Written by Chris Pressey of Cat's Eye Technologies.
This work is hereby placed in the public domain.
"""

import re
import types


class Stream(object):
    """
    A Stream is a kind of wrapper around an iterator which allows
    a limited form of look-ahead into the iterator's results.

    >>> def i():
    ...   for x in [6,1,7]:
    ...     yield x
    >>> s = Stream(i())
    >>> s.peek()
    6
    >>> s.peek()
    6
    >>> s.advance()
    >>> s.peek()
    1
    >>> s.advance()
    >>> s.peek()
    7
    >>> s.advance()
    >>> s.peek() is None
    True
    >>> s = Stream([1,2,3])
    >>> s.peek()
    1

    """

    def __init__(self, generator):
        self.buffer = []
        if isinstance(generator, types.GeneratorType):
            self.generator = generator
        else:
            def g():
                for x in generator:
                    yield x
            self.generator = g()

    def peek(self):
        if not self.buffer:
            try:
                self.buffer.append(next(self.generator))
            except StopIteration:
                return None
        return self.buffer[0]

    def advance(self):
        if not self.buffer:
            self.buffer.extend(next(self.generator))
        self.buffer.pop()


class RegLexer(object):
    """
    An iterator which, given a string, returns a generator which returns
    sucessive prefixes of the string based on supplied regexes.

    >>> t = RegLexer()
    >>> t.register(r'(\d+)',   meta='integer')
    >>> t.register(r'(\(|\))')
    >>> v = []
    >>> for n in t("12(34)"): v.append(n)
    >>> v
    [('integer', '12'), '(', ('integer', '34'), ')']
    >>> v = []
    >>> for n in t("12 ( 34 )"): v.append(n)
    >>> v
    [('integer', '12')]
    >>> t.ignore(r'\s+')
    >>> v = []
    >>> for n in t("12 ( 34 )"): v.append(n)
    >>> v
    [('integer', '12'), '(', ('integer', '34'), ')']

    """

    def __init__(self):
        self.text = ""
        self.patterns = []
        self.ignoring = []

    def __call__(self, text):
        self.text = text
        has_match = True
        while has_match:
            has_match = False
            has_ignore = True

            while has_ignore:
                has_ignore = False
                for pattern in self.ignoring:
                    result = re.match(pattern, self.text)
                    if result:
                        self.text = self.text[result.end():]
                        has_ignore = True
                        break

            for (pattern, meta) in self.patterns:
                result = re.match(pattern, self.text)
                if result:
                    self.text = self.text[result.end():]
                    has_match = True
                    break

            if has_match:
                if meta is not None:
                    yield meta, result.group()
                else:
                    yield result.group()

    def register(self, pattern, meta=None):
        self.patterns.append((pattern, meta))

    def ignore(self, pattern):
        self.ignoring.append(pattern)


class PredicateSet(object):
    """
    >>> s = PredicateSet('a','b','c')
    >>> 'a' in s
    True
    >>> 'z' in s
    False
    >>> s.add('z')
    >>> 'z' in s
    True
    >>> s.add(lambda x: x > 10)
    >>> 9 in s
    False
    >>> 12 in s
    True
    >>> 291 in s
    True
    >>> s.add(lambda x: x < 3)
    >>> 9 in s
    False
    >>> 12 in s
    True
    >>> 1 in s
    True

    """
    def __init__(self, *contents):
        self._set = set()
        self.update(contents)

    def add(self, entity):
        if callable(entity):
            self._set.add(entity)
        else:
            self._set.add(lambda x: x == entity)

    def update(self, iterable):
        for x in iterable:
            self.add(x)

    def __contains__(self, other):
        for x in self._set:
            if x(other):
                return True
        return False

    def __iter__(self):
        for x in self._set:
            yield x

    def __repr__(self):
        return "PredicateSet(%r)" % self._set


### Productions ###


class Production(object):
    constructor = None

    def parse(self, stream, grammar=None):
        """Subclasses should override this."""
        raise NotImplementedError

    def construct(self, constructor):
        self.constructor = constructor
        return self

    def capture(self, obj, grammar=None):
        if self.constructor is None:
            return obj
        else:
            return self.constructor(obj)

    def firsts(self, grammar=None):
        """Subclasses should override this."""
        return PredicateSet()

    def is_nullable(self, grammar=None):
        """Subclasses should override this."""
        return False


class Terminal(Production):
    """
    >>> t = Terminal('cat')
    >>> 'cat' in t.firsts()
    True
    >>> s = Stream(['cat'])
    >>> t.parse(s)
    'cat'
    >>> s = Stream(['cat','a','log'])
    >>> t.parse(s)
    'cat'
    >>> s.peek()
    'a'
    >>> s = Stream(['dog'])
    >>> t.parse(s) is None
    True
    """

    def __init__(self, entity):
        self.entity = entity

    def check_entity(self, against):
        if callable(self.entity):
            return self.entity(against)
        else:
            return against == self.entity

    def parse(self, stream, grammar=None):
        if self.check_entity(stream.peek()):
            result = self.capture(stream.peek(), grammar=grammar)
            stream.advance()
            return result
        return None

    def firsts(self, grammar=None):
        return PredicateSet(self.entity)


class Alternation(Production):
    """
    >>> a = Alternation(Terminal('cat'), Terminal('dog'))
    >>> 'cat' in a.firsts()
    True
    >>> 'dog' in a.firsts()
    True
    >>> s = Stream(['cat'])
    >>> a.parse(s)
    'cat'
    >>> s = Stream(['dog'])
    >>> a.parse(s)
    'dog'
    >>> s = Stream(['horse'])
    >>> a.parse(s) is None
    True
    """

    def __init__(self, *alternatives):
        self.alternatives = alternatives

    def parse(self, stream, grammar=None):
        for alternative in self.alternatives:
            if stream.peek() in alternative.firsts(grammar=grammar):
                result = alternative.parse(stream, grammar=grammar)
                return self.capture(result, grammar=grammar)
        return None

    def firsts(self, grammar=None):
        f = PredicateSet()
        for alternative in self.alternatives:
            f.update(alternative.firsts(grammar=grammar))
        return f

    def is_nullable(self, grammar=None):
        for alternative in self.alternatives:
            if alternative.is_nullable(grammar=grammar):
                return True
        return False


class Sequence(Production):
    """
    >>> p = Sequence(Terminal('cat'), Terminal('dog'))
    >>> 'cat' in p.firsts()
    True
    >>> 'dog' in p.firsts()
    False
    >>> p.parse(Stream(['cat','food'])) is None
    True
    >>> p.parse(Stream(['dog','food'])) is None
    True
    >>> p.parse(Stream(['cat','dog']))
    ['cat', 'dog']
    """

    def __init__(self, *sequence):
        self.sequence = sequence

    def parse(self, stream, grammar=None):
        results = []
        for component in self.sequence:
            result = component.parse(stream, grammar=grammar)
            if result is None:
                results = None
                break
            results.append(result)
        if results is not None:
            return self.capture(results, grammar=grammar)
        return None

    def firsts(self, grammar=None):
        f = PredicateSet()
        for component in self.sequence:
            f.update(component.firsts(grammar=grammar))
            if not component.is_nullable(grammar=grammar):
                break
        return f

    def is_nullable(self, grammar=None):
        for component in self.sequence:
            if not component.is_nullable(grammar=grammar):
                return False
        return True


class Asteration(Production):
    """
    >>> p = Asteration(Terminal('cat'))
    >>> 'cat' in p.firsts()
    True
    >>> s = Stream(['cat'])
    >>> p.parse(s)
    ['cat']
    >>> s.peek() is None
    True
    >>> s = Stream(['cat','cat','cat'])
    >>> p.parse(s)
    ['cat', 'cat', 'cat']
    >>> s.peek() is None
    True
    >>> s = Stream(['dog'])
    >>> p.parse(s)
    []
    >>> s.peek()
    'dog'

    >>> p = Sequence(Asteration(Terminal('cat')), Terminal('dog'))
    >>> p.parse(Stream(['cat'])) is None
    True
    >>> p.parse(Stream(['cat','dog']))
    [['cat'], 'dog']
    >>> p.parse(Stream(['cat','cat','cat','dog']))
    [['cat', 'cat', 'cat'], 'dog']
    >>> p.parse(Stream(['dog']))
    [[], 'dog']
    """

    def __init__(self, production):
        self.production = production

    def parse(self, stream, grammar=None):
        results = []
        while stream.peek() in self.production.firsts(grammar=grammar):
            result = self.production.parse(stream, grammar=grammar)
            if result is None:
                break
            results.append(result)
        return self.capture(results, grammar=grammar)

    def firsts(self, grammar=None):
        return self.production.firsts(grammar=grammar)

    def is_nullable(self, grammar=None):
        return True


class Optional(Production):
    """
    >>> p = Optional(Terminal('cat'))
    >>> 'cat' in p.firsts()
    True
    >>> s = Stream(['cat'])
    >>> p.parse(s)
    ['cat']
    >>> s.peek() is None
    True
    """

    def __init__(self, production):
        self.production = production

    def parse(self, stream, grammar=None):
        results = []
        if stream.peek() in self.production.firsts(grammar=grammar):
            result = self.production.parse(stream, grammar=grammar)
            if result is not None:
                results.append(result)
        return self.capture(results, grammar=grammar)

    def firsts(self, grammar=None):
        return self.production.firsts(grammar=grammar)

    def is_nullable(self, grammar=None):
        return True


class NonTerminal(Production):
    def __init__(self, name):
        self.name = name

    def _production(self, grammar):
        if not grammar:
            raise TypeError("need grammar to use NonTerminal")
        return grammar[self.name]

    def parse(self, stream, grammar=None):
        result = self._production(grammar).parse(stream, grammar=grammar)
        return self.capture(result, grammar=grammar)

    def firsts(self, grammar=None):
        return self._production(grammar).firsts(grammar=grammar)

    def is_nullable(self, grammar=None):
        return self._production(grammar).is_nullable(grammar=grammar)


class Grammar(object):
    """Container for a set of named productions.

    >>> g = Grammar()
    >>> g['Expr'] = Sequence(
    ...   Terminal('('),Asteration(Terminal('*')),Terminal(')'))
    >>> g.parse('Expr', Stream(['(','*','*',')']))
    ['(', ['*', '*'], ')']
    >>> g['Expr'] = Sequence(
    ...   Terminal('('),Asteration(NonTerminal('Expr')),Terminal(')'))
    >>> g.parse('Expr', Stream(['(',')']))
    ['(', [], ')']
    >>> s = Stream(['(','(',')',')'])
    >>> g.parse('Expr', s)
    ['(', [['(', [], ')']], ')']
    >>> s.peek() is None
    True
    >>> g.parse('Expr', Stream(['(','(',')'])) is None
    True
    """

    trace = False

    def __init__(self, parent=None):
        self.productions = {}
        self.parent = parent

    def __getitem__(self, key):
        if self.trace:
            print("Reading production ", key)
        if key in self.productions:
            return self.productions[key]
        elif self.parent:
            return self.parent[key]
        else:
            raise KeyError("No production '%s' in grammar, and "
                           "no parent grammar" % key)

    def __setitem__(self, key, value):
        self.productions[key] = value

    def parse(self, name, stream):
        return self[name].parse(stream, grammar=self)


if __name__ == "__main__":
    import doctest
    doctest.testmod()
