#!/usr/bin/python
# -*- coding: utf-8 -*-

"""
Test suite for (Python implementations of) the Eightebed programming language.
"""


class Tests(object):
    """Class containing test cases for Eightebed.

    >>> from .parser import parse, Eightebed
    >>> from .drivers import parse_and_check, load_and_go
    >>> p = parse(Tests.simple_ok)
    >>> isinstance(p, Eightebed)
    True
    >>> p.typedecls
    []
    >>> p.vardecls
    [VarDecl('jim', TypeInt())]
    >>> p.block
    Block([AssignStmt(VarRef('jim'), IntConst(4))])
    >>> p = parse_and_check(Tests.simple_ok)

    >>> parse_and_check(Tests.double_declaration)
    Traceback (most recent call last):
    ...
    KeyError: 'jim already declared'

    >>> parse_and_check(Tests.ptr_to_ptr)
    Traceback (most recent call last):
    ...
    TypeError: Pointer type must point to named type

    >>> parse_and_check(Tests.ptr_to_int)
    Traceback (most recent call last):
    ...
    TypeError: Pointer type must point to named type

    >>> parse_and_check(Tests.struct_within_struct)
    Traceback (most recent call last):
    ...
    TypeError: Structs may not contain other structs

    >>> parse_and_check(Tests.named_int)
    Traceback (most recent call last):
    ...
    TypeError: Only structs may be named

    >>> parse_and_check(Tests.dereference_outside_conditional)
    Traceback (most recent call last):
    ...
    TypeError: Attempt to dereference jim in non-safe context

    >>> parse_and_check(Tests.dereference_outside_safe_area)
    Traceback (most recent call last):
    ...
    TypeError: Attempt to dereference jim in non-safe context

    >>> p = parse_and_check(Tests.dereference_within_nested_safe_area)
    >>> p is None
    False

    >>> parse_and_check(Tests.dereference_after_free)
    Traceback (most recent call last):
    ...
    TypeError: Attempt to dereference jim in non-safe context

    Hey!  Enough of the static tests.  Let's run some actual Eightebed
    programs and check their output.

    >>> p = parse_and_check(Tests.allocated_values_initialized)
    >>> load_and_go(p)
    '0 '

    >>> p = parse_and_check(Tests.simple_arith)
    >>> load_and_go(p)
    '4 '

    >>> p = parse_and_check(Tests.loop_1)
    >>> load_and_go(p)
    '5 4 3 2 1 '

    >>> p = parse_and_check(Tests.allocating_loop)
    >>> load_and_go(p)
    ''

    >>> p = parse_and_check(Tests.free_invalidates)
    >>> load_and_go(p)
    '53 '

    >>> p = parse_and_check(Tests.alias_is_invalidated)
    >>> load_and_go(p)
    '100 99 98 97 96 95 94 93 92 91 90 89 88 '

    In principle, this test demonstrates that the memory freed by the
    free command can be re-used by a subsequent malloc expression.  Of
    course, since nothing is actually forcing the backend C compiler's
    implementation of malloc() to re-use memory that was previously
    free()'d, we don't actually test it here.

    >>> p = parse_and_check(Tests.allocate_and_free_loop)
    >>> load_and_go(p)
    '50 '

    """
    simple_ok = """\
    var int jim;
    {
        jim = 4;
    }
"""
    simple_arith = """\
    {
        if (((3 * 3) = (10 - 1)) & (4 > 3)) {
            print ((4 + 8) / 3);
        }
    }
"""
    double_declaration = """\
    var int jim;
    var ptr to node jim;
    {
        print 3;
    }
"""
    ptr_to_ptr = """\
    type node struct {
        int value;
        ptr to ptr to node next;
    };
    var node jim;
    {
        print [jim].value;
    }
"""
    ptr_to_int = """\
    var ptr to int kelly;
    {
        if valid kelly { print @kelly; }
    }
"""
    struct_within_struct = """\
    type kooba struct {
        int value;
        struct {
            int whirlygig;
        } barnard;
    };
    var kooba jim;
    {
        print [jim].value;
    }
"""
    named_int = """\
    type kooba int;
    var kooba jim;
    {
        print jim;
    }
"""
    dereference_outside_conditional = """\
    type node struct {
        int value;
        ptr to node next;
    };
    var ptr to node jim;
    {
        jim = malloc node;
        print [@jim].value;
        free jim;
    }
"""
    dereference_outside_safe_area = """\
    type node struct {
        int value;
        ptr to node next;
    };
    var ptr to node jim;
    var ptr to node murray;
    {
        jim = malloc node;
        if valid jim {
            jim = murray;
            print [@jim].value;
        }
        free jim;
    }
"""
    dereference_after_free = """\
    type node struct {
        int value;
        ptr to node next;
    };
    var ptr to node jim;
    var ptr to node donald;
    {
        jim = malloc node;
        donald = jim;
        if valid jim {
            free donald;
            print [@jim].value;
        }
    }
"""
    dereference_within_nested_safe_area = """\
    type node struct {
        int value;
        ptr to node next;
    };
    var ptr to node jim;
    {
        jim = malloc node;
        if valid jim {
            [@jim].next = malloc node;
        }
        if valid jim {
            if valid [@jim].next {
                print [@jim].value;
            }
        }
        free jim;
    }
"""
    allocated_values_initialized = """\
    type node struct {
        int value;
        ptr to node next;
    };
    var ptr to node jim;
    var ptr to node nestor;
    {
        jim = malloc node;
        if valid jim {
            print [@jim].value;
            nestor = [@jim].next;
            if valid nestor {
                print 99;
            }
        }
        free jim;
    }
"""
    loop_1 = """\
    var int i;
    {
        i = 5;
        while i {
            print i;
            i = (i - 1);
        }
    }
"""
    allocating_loop = """\
    type node struct {
        int value;
        ptr to node next;
    };
    var ptr to node jim;
    var ptr to node harry;
    var int i;
    {
        jim = malloc node;
        harry = jim;
        i = 100;
        while i {
            harry = malloc node;
            if valid jim {
                [@jim].value = i;
            }
            if valid jim {
                [@jim].next = harry;
                if valid harry {
                    jim = harry;
                }
            }
            i = (i - 1);
        }
    }
"""
    free_invalidates = """\
    type node struct {
        int value;
        ptr to node next;
    };
    var ptr to node jim;
    {
        jim = malloc node;
        if valid jim {
            free jim;
        }
        if valid jim {
            print 42;
        }
        print 53;
    }
"""
    alias_is_invalidated = """\
    type node struct {
        int value;
        ptr to node next;
    };
    var ptr to node jim;
    var ptr to node harry;
    var ptr to node bertie;
    var ptr to node albert;
    var int i;
    {
        albert = malloc node;
        jim = albert;
        harry = jim;
        i = 100;
        while i {
            harry = malloc node;
            if valid jim {
                [@jim].value = i;
            }
            if (i = 87) {
                bertie = jim;
            }
            if valid jim {
                [@jim].next = harry;
                if valid harry {
                    jim = harry;
                }
            }
            i = (i - 1);
        }
        free bertie;
        jim = albert;
        while valid jim {
            if valid jim {
                print [@jim].value;
                jim = [@jim].next;
            }
        }
    }
"""
    allocate_and_free_loop = """\
    type node struct {
        int value;
        ptr to node next;
    };
    var ptr to node fred;
    var ptr to node george;
    var int i;
    {
        i = 100;
        while i {
            fred = malloc node;
            if valid fred {
                [@fred].value = i;
            }
            if (i = 50) {
                george = fred;
            } else {
                free fred;
            }
            i = (i - 1);
        }
        if valid george {
            print [@george].value;
        }
    }
"""


if __name__ == "__main__":
    import doctest
    doctest.testmod()
