# -*- coding: utf-8 -*-

"""
Parser for the Eightebed programming language.
"""

import logging
import re

from .rooibos import (Stream, RegLexer,
                      Terminal, NonTerminal,
                      Alternation, Sequence, Asteration, Optional,
                      Grammar)
from .context import Context


logger = logging.getLogger("parser")


class TypeError(RuntimeError):
    pass


class Eightebed(object):
    def __init__(self, data):
        self.typedecls = data[0]
        self.vardecls = data[1]
        self.block = data[2]

    def __repr__(self):
        return "%s(%s, %s, %s)" % (
            self.__class__.__name__,
            repr(self.typedecls), repr(self.vardecls), repr(self.block)
        )

    def typecheck(self, types, vars):
        for typedecl in self.typedecls:
            typedecl.typecheck(types, vars)
        for vardecl in self.vardecls:
            vardecl.typecheck(types, vars)
        self.block.typecheck(types, vars)

    def vanalyze(self, context):
        self.block.vanalyze(context)

    def emit(self, stream, options):
        stream.write("""\
/* Achtung!  This Source was Automatically Generated by %s! */
#include <stdlib.h>
#include <stdio.h>
#include <string.h>
#include <assert.h>

""" % options.pedigree)
        if options.trace_marking:
            stream.write("#define TRACE_MARKING 1\n")
        stream.write("""\
typedef struct _ptr {
  void *p;
  int valid;
} _ptr;

static void _8ebed_invalidate(_ptr *ptr) {
  ptr->valid = 0;
}

static int _8ebed_valid(_ptr ptr) {
  return ptr.valid;
}

static int _8ebed_is_alias(_ptr a, _ptr b) {
  return a.p == b.p;
}

static _ptr _8ebed_malloc(size_t size) {
  _ptr ptr;
  ptr.p = malloc(size);
  ptr.valid = (ptr.p != NULL);
  if (ptr.p != NULL) {
    memset(ptr.p, 0, size);
  }
  return ptr;
}

static void _mark__root(_ptr);
static void _8ebed_free(_ptr *ptr) {
  if (!_8ebed_valid(*ptr)) return;
  _mark__root(*ptr);
  free(ptr->p);
  _8ebed_invalidate(ptr);
}

""")
        for typedecl in self.typedecls:
            typedecl.emit(stream, options)
        for vardecl in self.vardecls:
            vardecl.emit(stream)
        stream.write(r"""\
static void _mark__root(_ptr outcast) {
#ifdef TRACE_MARKING
fprintf(stderr, "-> BEGIN marking %s @root\n", (long)outcast.p);
#endif
""" % options.pointer_format)
        for vardecl in self.vardecls:
            vardecl.emit_marker(stream)
        stream.write(r"""
#ifdef TRACE_MARKING
fprintf(stderr, "-> END marking %s @root\n", (long)outcast.p);
#endif
}

int main(int argc, char **argv) {
""" % options.pointer_format)
        self.block.emit(stream)
        stream.write("}\n")


class Block(object):
    def __init__(self, data):
        self.stmts = data[1]

    def __repr__(self):
        return "%s(%s)" % (self.__class__.__name__, repr(self.stmts))

    def typecheck(self, types, vars):
        block_types = Context(parent=types)
        block_vars = Context(parent=vars)
        for stmt in self.stmts:
            stmt.typecheck(block_types, block_vars)

    def vanalyze(self, context):
        for stmt in self.stmts:
            stmt.vanalyze(context)

    def emit(self, stream):
        for stmt in self.stmts:
            stmt.emit(stream)


class TypeDecl(object):
    def __init__(self, data):
        self.name = data[1]
        self.type = data[2]

    def __repr__(self):
        return "TypeDecl(%s, %s)" % (repr(self.name), repr(self.type))

    def typecheck(self, types, vars):
        types.declare(self.name, self.type)
        self.type.typecheck(types, vars)
        if not isinstance(self.type, TypeStruct):
            raise TypeError("Only structs may be named")
        return self.type

    def emit(self, stream, options):
        if isinstance(self.type, TypeStruct):
            stream.write("typedef \n")
            self.type.emit_forward(stream)
            stream.write(" %s;\n" % self.name)
            self.type.emit(stream)
            stream.write(";\n")
            stream.write("static void mark_%s(_ptr outcast, %s* p) {" %
                         (self.name, self.name))
            marking_text = (options.pointer_format + (" @%s " % self.name) +
                            options.pointer_format)
            stream.write(r"""
#ifdef TRACE_MARKING
fprintf(stderr, "-> BEGIN marking %s\n", (long)outcast.p, (long)p);
#endif
""" % marking_text)
            for member in self.type.members:
                if isinstance(member.type, TypePtr):
                    stream.write("""
  if (_8ebed_is_alias(outcast, p->%s)) {
    _8ebed_invalidate(&p->%s);
  } else if (_8ebed_valid(p->%s)) {
    mark_""" % (member.name, member.name, member.name))
                    member.type.points_to().emit(stream)
                    stream.write("(outcast, (")
                    member.type.points_to().emit(stream)
                    stream.write(" *)(p->%s.p));\n  }\n" % member.name)
            stream.write(r"""
#ifdef TRACE_MARKING
fprintf(stderr, "-> END marking %s\n", (long)outcast.p, (long)p);
#endif
}
""" % marking_text)
        else:
            stream.write("typedef \n")
            self.type.emit(stream)
            stream.write(" %s;\n" % self.name)
        stream.write("\n")

# These classes double as AST components and as type expressions.


class Type(object):
    def equiv(self, other):
        raise NotImplementedError

    def points_to(self):
        return None

    def resolve(self, types):
        return self

    def get_member_type(self, name):
        return None


class TypeVoid(Type):
    def __init__(self, data=None):
        pass

    def equiv(self, other):
        return isinstance(other, TypeVoid)

    def emit(self, stream):
        stream.write("void")


class TypeInt(Type):
    def __init__(self, data=None):
        pass

    def __repr__(self):
        return "%s()" % (self.__class__.__name__)

    def typecheck(self, types, vars):
        return self

    def equiv(self, other):
        return isinstance(other, TypeInt)

    def emit(self, stream):
        stream.write("int")


struct_id = 0


class TypeStruct(Type):
    def __init__(self, data):
        global struct_id
        self.members = data[2]
        self.id = struct_id
        struct_id += 1

    def __repr__(self):
        return "%s(%s)" % (self.__class__.__name__, repr(self.members))

    def typecheck(self, types, vars):
        for member in self.members:
            type_ = member.typecheck(types, vars)
            if isinstance(type_, TypeStruct):
                raise TypeError("Structs may not contain other structs")
        return self

    def equiv(self, other):
        return False

    def emit(self, stream):
        stream.write("struct s_%s {\n" % self.id)
        for member in self.members:
            member.emit(stream)
        stream.write("}")

    def emit_forward(self, stream):
        stream.write("struct s_%s" % self.id)

    def get_member_type(self, name):
        for decl in self.members:
            if decl.name == name:
                return decl.type
        return None


class TypePtr(Type):
    def __init__(self, data):
        self.target = data[2]

    def __repr__(self):
        return "%s(%s)" % (self.__class__.__name__, repr(self.target))

    def typecheck(self, types, vars):
        self.target.typecheck(types, vars)
        if isinstance(self.target, TypeNamed):
            return self
        else:
            raise TypeError("Pointer type must point to named type")

    def equiv(self, other):
        return isinstance(other, TypePtr) and self.target.equiv(other.target)

    def points_to(self):
        return self.target

    def emit(self, stream):
        stream.write("/* ")
        self.target.emit(stream)
        stream.write("*")
        stream.write(" */ ")
        stream.write("_ptr")


class TypeNamed(Type):
    def __init__(self, data):
        self.name = data

    def __repr__(self):
        return "%s(%s)" % (self.__class__.__name__, repr(self.name))

    def typecheck(self, types, vars):
        return True  # can't look self up yet, might not exist yet

    def equiv(self, other):
        return isinstance(other, TypeNamed) and self.name == other.name

    def emit(self, stream):
        stream.write(self.name)

    def resolve(self, types):
        return types.lookup(self.name)


class Decl(object):
    def __init__(self, data):
        self.type = data[0]
        self.name = data[1]

    def __repr__(self):
        return "%s(%r, %r)" % (self.__class__.__name__, self.name, self.type)

    def typecheck(self, types, vars):
        self.type.typecheck(types, vars)
        return self.type

    def emit(self, stream):
        self.type.emit(stream)
        stream.write(" %s;\n" % self.name)


class VarDecl(object):
    def __init__(self, data):
        decl = data[1]
        self.type = decl.type
        self.name = decl.name

    def __repr__(self):
        return "%s(%s, %s)" % (self.__class__.__name__, repr(self.name), repr(self.type))

    def typecheck(self, types, vars):
        self.type.typecheck(types, vars)
        vars.declare(self.name, self.type)
        return self.type

    def emit(self, stream):
        self.type.emit(stream)
        stream.write(" %s;\n" % self.name)

    def emit_marker(self, stream):
        if isinstance(self.type, TypePtr):
            stream.write("""
  if (_8ebed_is_alias(outcast, %s)) {
    _8ebed_invalidate(&%s);
  } else if (_8ebed_valid(%s)) {
    mark_""" % (self.name, self.name, self.name))
            self.type.points_to().emit(stream)
            stream.write("(outcast, (")
            self.type.points_to().emit(stream)
            stream.write(" *)%s.p);\n  }\n" % self.name)


class WhileStmt(object):
    def __init__(self, data):
        self.expr = data[1]
        self.block = data[2]

    def __repr__(self):
        return "%s(%s, %s)" % (self.__class__.__name__, repr(self.expr), repr(self.block))

    def typecheck(self, types, vars):
        self.expr.typecheck(types, vars)
        self.block.typecheck(types, vars)
        return TypeVoid()

    def vanalyze(self, context):
        self.expr.vanalyze(context)
        self.block.vanalyze(context)

    def emit(self, stream):
        stream.write("while(")
        self.expr.emit(stream)
        stream.write(") {\n")
        self.block.emit(stream)
        stream.write("}\n")


class IfStmt(object):
    def __init__(self, data):
        self.expr = data[1]
        self.then = data[2]
        elsepart = data[3]
        if elsepart:
            self.else_ = elsepart[0][1]
        else:
            self.else_ = Block(['{', [], '}'])

    def __repr__(self):
        return "%s(%s, %s, %s)" % (self.__class__.__name__, repr(self.expr), repr(self.then), repr(self.else_))

    def typecheck(self, types, vars):
        self.expr.typecheck(types, vars)
        self.then.typecheck(types, vars)
        self.else_.typecheck(types, vars)
        return TypeVoid()

    def vanalyze(self, context):
        self.expr.vanalyze(context)
        # If the test expr is exactly "valid x", put x into context,
        # asserting that it is valid hereafter in this block
        subcontext = Context(parent=context)
        if isinstance(self.expr, ValidExpr):
            if isinstance(self.expr.expr, VarRef):
                subcontext[self.expr.expr.name] = True
        self.then.vanalyze(subcontext)
        self.else_.vanalyze(context)

    def emit(self, stream):
        stream.write("if(")
        self.expr.emit(stream)
        stream.write(") {\n")
        self.then.emit(stream)
        stream.write("} else {\n")
        self.else_.emit(stream)
        stream.write("}\n")


class FreeStmt(object):
    def __init__(self, data):
        self.ref = data[1]

    def __repr__(self):
        return "%s(%s)" % (self.__class__.__name__, repr(self.ref))

    def typecheck(self, types, vars):
        ref_type = self.ref.typecheck(types, vars)
        if ref_type.points_to() is None:
            raise TypeError("%r is not a pointer type" % ref_type)
        return TypeVoid()

    def vanalyze(self, context):
        self.ref.vanalyze(context)
        # End safe area -- remove all assertions of validity hereafter.
        context.empty()

    def emit(self, stream):
        stream.write("_8ebed_free(&")
        self.ref.emit(stream)
        stream.write(");\n")


class PrintStmt(object):
    def __init__(self, data):
        self.expr = data[1]

    def __repr__(self):
        return "%s(%s)" % (self.__class__.__name__, repr(self.expr))

    def typecheck(self, types, vars):
        expr_type = self.expr.typecheck(types, vars)
        if not expr_type.equiv(TypeInt()):
            raise TypeError("%r is not an int" % expr_type)
        return TypeVoid()

    def vanalyze(self, context):
        self.expr.vanalyze(context)

    def emit(self, stream):
        stream.write("printf(\"%d \", ")
        self.expr.emit(stream)
        stream.write(");\n")


class AssignStmt(object):
    def __init__(self, data):
        self.ref = data[0]
        self.expr = data[2]

    def __repr__(self):
        return "%s(%s, %s)" % (self.__class__.__name__, repr(self.ref), repr(self.expr))

    def typecheck(self, types, vars):
        tlhs = self.ref.typecheck(types, vars)
        trhs = self.expr.typecheck(types, vars)
        if trhs.equiv(tlhs):
            return TypeVoid()
        else:
            raise TypeError("%r (%r) not equivalent to %r (%r) for vars %s" %
                            (tlhs, self.ref, trhs, self.expr, vars))

    def vanalyze(self, context):
        self.ref.vanalyze(context)
        self.expr.vanalyze(context)
        # End safe area -- remove all assertions of validity hereafter.
        context.empty()

    def emit(self, stream):
        self.ref.emit(stream)
        stream.write(" = ")
        self.expr.emit(stream)
        stream.write(";\n")


class BinOpExpr(object):
    map = {
        '+': '+',
        '-': '-',
        '*': '*',
        '/': '/',
        '=': '==',
        '>': '>',
        '&': '&&',
        '|': '||',
    }

    def __init__(self, data):
        self.lhs = data[1]
        self.op = data[2]
        self.rhs = data[3]

    def __repr__(self):
        return "%s(%s, %s, %s)" % (self.__class__.__name__, repr(self.lhs), repr(self.op), repr(self.rhs))

    def typecheck(self, types, vars):
        trhs = self.lhs.typecheck(types, vars)
        tlhs = self.rhs.typecheck(types, vars)
        if not tlhs.equiv(TypeInt()):
            raise TypeError("lhs %r is not an int" % tlhs)
        if not trhs.equiv(TypeInt()):
            raise TypeError("rhs %r is not an int" % trhs)
        return TypeInt()

    def vanalyze(self, context):
        self.lhs.vanalyze(context)
        self.rhs.vanalyze(context)

    def emit(self, stream):
        stream.write("(")
        self.lhs.emit(stream)
        stream.write(" %s " % self.map[self.op])
        self.rhs.emit(stream)
        stream.write(")")


class MallocExpr(object):
    def __init__(self, data):
        self.type = data[1]

    def __repr__(self):
        return "%s(%s)" % (self.__class__.__name__, repr(self.type))

    def typecheck(self, types, vars):
        return TypePtr(['', '', self.type])

    def vanalyze(self, context):
        pass

    def emit(self, stream):
        stream.write("_8ebed_malloc(sizeof(")
        self.type.emit(stream)
        stream.write("))")


class ValidExpr(object):
    def __init__(self, data):
        self.expr = data[1]

    def __repr__(self):
        return "%s(%s)" % (self.__class__.__name__, repr(self.expr))

    def typecheck(self, types, vars):
        expr_type = self.expr.typecheck(types, vars)
        if expr_type.points_to() is None:
            raise TypeError("%r is not a pointer type" % expr_type)
        return TypeInt()

    def vanalyze(self, context):
        self.expr.vanalyze(context)

    def emit(self, stream):
        stream.write("_8ebed_valid(")
        self.expr.emit(stream)
        stream.write(")")


class DottedRef(object):
    def __init__(self, data):
        self.source = data[1]
        self.member_name = data[4]

    def __repr__(self):
        return "%s(%s, %s)" % (self.__class__.__name__, repr(self.source), repr(self.member_name))

    def typecheck(self, types, vars):
        source_type = self.source.typecheck(types, vars)
        source_type = source_type.resolve(types)
        member_type = source_type.get_member_type(self.member_name)
        if member_type is None:
            raise TypeError("%r does not have member %s" %
                            (source_type, self.member_name))
        return member_type

    def vanalyze(self, context, deref=False):
        self.source.vanalyze(context, deref=deref)

    def emit(self, stream):
        self.source.emit(stream)
        stream.write(".%s" % self.member_name)


class DeRef(object):
    def __init__(self, data):
        self.source = data[1]
        self._dest_type = None

    def __repr__(self):
        return "%s(%s)" % (self.__class__.__name__, repr(self.source))

    def typecheck(self, types, vars):
        source_type = self.source.typecheck(types, vars)
        dest_type = source_type.points_to()
        if dest_type is None:
            raise TypeError("%r is not a pointer type" % source_type)
        self._dest_type = dest_type
        return dest_type

    def vanalyze(self, context, deref=False):
        self.source.vanalyze(context, deref=True)

    def emit(self, stream):
        stream.write("(*(")
        self._dest_type.emit(stream)
        stream.write(" *)")
        self.source.emit(stream)
        stream.write(".p)")


class VarRef(object):
    def __init__(self, data):
        self.name = data

    def __repr__(self):
        return "%s(%s)" % (self.__class__.__name__, repr(self.name))

    def typecheck(self, types, vars):
        #if self.name == 'i':
        #    raise NotImplementedError, vars.lookup(self.name)
        return vars.lookup(self.name)

    def vanalyze(self, context, deref=False):
        if deref:
            if not context.lookup(self.name, default=False):
                raise TypeError("Attempt to dereference %s "
                                "in non-safe context" % self.name)

    def emit(self, stream):
        stream.write(self.name)


class IntConst(object):
    def __init__(self, data):
        self.value = int(data)

    def __repr__(self):
        return "%s(%s)" % (self.__class__.__name__, repr(self.value))

    def typecheck(self, types, vars):
        return TypeInt()

    def vanalyze(self, context, deref=False):
        pass

    def emit(self, stream):
        stream.write(str(self.value))


g = Grammar()
g['Eightebed'] = Sequence(Asteration(NonTerminal('TypeDecl')),
                          Asteration(NonTerminal('VarDecl')),
                          NonTerminal('Block')).construct(Eightebed)
g['Block']    = Sequence(Terminal('{'),
                         Asteration(NonTerminal('Stmt')),
                         Terminal('}')).construct(Block)
g['TypeDecl'] = Sequence(Terminal('type'),
                         NonTerminal('TypeName'),
                         NonTerminal('Type'),
                         Terminal(';')).construct(TypeDecl)
g['Type']     = Alternation(Terminal('int').construct(TypeInt),
                            Sequence(Terminal('struct'), Terminal('{'), Asteration(NonTerminal('Decl')), Terminal('}')).construct(TypeStruct),
                            Sequence(Terminal('ptr'), Terminal('to'), NonTerminal('Type')).construct(TypePtr),
                            NonTerminal('TypeName').construct(TypeNamed))
g['Decl']     = Sequence(NonTerminal('Type'),
                         NonTerminal('VarName'),
                         Terminal(';')).construct(Decl)
g['VarDecl']  = Sequence(Terminal('var'), NonTerminal('Decl')).construct(VarDecl)
g['Stmt']     = Alternation(Sequence(Terminal('while'), NonTerminal('Expr'), NonTerminal('Block')).construct(WhileStmt),
                            Sequence(Terminal('if'), NonTerminal('Expr'), NonTerminal('Block'),
                                     Optional(Sequence(Terminal('else'), NonTerminal('Block')))).construct(IfStmt),
                            Sequence(Terminal('free'), NonTerminal('Ref'), Terminal(';')).construct(FreeStmt),
                            Sequence(Terminal('print'), NonTerminal('Expr'), Terminal(';')).construct(PrintStmt),
                            Sequence(NonTerminal('Ref'), Terminal('='), NonTerminal('Expr'), Terminal(';')).construct(AssignStmt))
g['Ref']      = Alternation(Sequence(Terminal('['), NonTerminal('Ref'), Terminal(']'), Terminal('.'), NonTerminal('VarName')).construct(DottedRef),
                            Sequence(Terminal('@'), NonTerminal('Ref')).construct(DeRef),
                            NonTerminal('VarName').construct(VarRef))
g['Expr']     = Alternation(Sequence(Terminal('('), NonTerminal('Expr'), NonTerminal('BinOp'), NonTerminal('Expr'), Terminal(')')).construct(BinOpExpr),
                            Sequence(Terminal('malloc'), NonTerminal('Type')).construct(MallocExpr),
                            Sequence(Terminal('valid'), NonTerminal('Expr')).construct(ValidExpr),
                            NonTerminal('IntLit').construct(IntConst),
                            NonTerminal('Ref'))
g['BinOp']    = Alternation(Terminal('+'), Terminal('-'), Terminal('*'),
                            Terminal('/'), Terminal('='), Terminal('>'),
                            Terminal('&'), Terminal('|'))

g['TypeName'] = Terminal(lambda x: re.match('^[a-zA-Z]\w*$', x))
g['VarName']  = Terminal(lambda x: re.match('^[a-zA-Z]\w*$', x))
g['IntLit']   = Terminal(lambda x: re.match('^\d+$', x))


def parse(text):
    r = RegLexer()
    r.ignore(r'\s+')
    r.register(r'(\d+)')
    r.register(r'(\(|\)|\[|\]|\;|\{|\}|\=|\+|\-|\*|\/|\,|\@|\.|\>|\&|\|)')
    r.register(r'([a-zA-Z]\w*)')
    s = Stream(r(text))
    return g.parse('Eightebed', s)


def parse_file(filename):
    f = open(filename, "r")
    contents = f.read()
    f.close()
    return parse(contents)


if __name__ == "__main__":
    import doctest
    doctest.testmod()
