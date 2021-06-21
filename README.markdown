The Eightebed Programming Language
==================================

Language version 1.1

Abstract
--------

While discussing [Cyclone](http://cyclone.thelanguage.org/), Gregor
Richards stated that in order for a language to support explicit
`malloc()`ing and `free()`ing of allocated memory, while also being safe
(in the sense of not being able to execute or dereference
incorrectly-populated memory) would require that language to either
support garbage collection, or to not implement `free()`. In his words:

> A C-like language which provides a true explicit free() cannot be
> safe. (By "true" I mean that you can get that memory back in a later
> malloc().) To be safe a language must either never free (which is bad)
> or be GC'd. [C-like languages being] imperative languages with
> pointers at arbitrary data, where safety is defined as not seeing that
> data as a different type.

Eightebed was designed as a counterexample to that claim. Eightebed is a
small, C-like language with explicit `malloc()` and `free()`. Memory is
actually freed by `free()` and might be re-allocated by a future
`malloc()`. Yet Eightebed is a safe language, requiring only a modicum
of static analysis and runtime support, and in particular, it neither
specifies nor requires garbage collection:

-   Garbage, reasonably defined as "any unreachable block of memory", is
    disregarded and considered a memory leak, as is good and proper (or
    at least accepted) in a language with explicit memory management;
    and
-   Nothing is collected in any way.

Without Loss of Generality
--------------------------

We place some restrictions on Eightebed in order that our implementation
of a compiler and analyzer for it may be simplified. These restrictions
do not, we assert, prevent the language from being "C-like", as it would
be possible to extend the language to include them; the only thing we
would be adding if we were to do so would be additional complexity in
implementation. These restrictions are:

-   There are no functions in Eightebed. Common functionality can be
    repeated verbatim inline, and recursion can be replaced with `while`
    loops.
-   Pointers may only point to named types, not integers or other
    pointers, and only structures may be named. The effect of a pointer
    to an integer or pointer may be easily achieved by pointing to a
    named structure which consists of only an integer or pointer itself.
-   Structures may not contain structures. Again, this can be easily
    simulated by "flattening" the structure into a single structure with
    perhaps differentiated names.

Syntax
------

### EBNF Grammar

Note that where this grammar is a little weird, it is only to support
being fully LL(1) to ease parser construction. Notably, the syntax to
access a member of a structure uses both square brackets around the
structure and a dot between structure and member. Unlike C, there is no
syntax like `->` to dereference and access a member in one go; you need
to dereference with `@`, then access the member with `[].`.

    Eightebed ::= {TypeDecl} {VarDecl} Block.
    Block     ::= "{" {Stmt} "}".
    TypeDecl  ::= "type" NameType Type ";"
    Type      ::= "int"
                | "struct" "{" {Decl} "}"
                | "ptr" "to" Type
                | NameType.
    Decl      ::= Type Name ";".
    VarDecl   ::= "var" Decl.
    Stmt      ::= "while" Expr Block
                | "if" Expr Block ["else" Block]
                | "free" Ref ";"
                | "print" Expr ";"
                | Ref "=" Expr ";".
    Ref       ::= "[" Ref "]" "." Name
                | "@" Ref
                | Name.
    Expr      ::= "(" Expr ("+"|"-"|"*"|"/"|"="|">"|"&"|"|") Expr ")"
                | "malloc" NameType
                | "valid" Expr
                | IntLit
                | Ref.

### Example Program

    type node struct {
        int value;
        ptr to node next;
    };
    var ptr to node jim;
    var ptr to node george;
    {    
        jim = malloc node;
        if valid jim {
            [@jim].value = (1 + 4);
            george = jim;
        }
        if valid george {
            print [@george].value;
        }
        free george;
        free jim;
    }

How it Works
------------

### Static Analysis

Dereferencing a pointer x must only occur at the _safe start_ of the
"then" part of an `if` statement whose test condition consists only of
the expression `valid x`. The safe start of a block is the set of
statements preceding and including the first assignment statement or
`free`. (This is on the [admittedly somewhat pessimistic] assumption
that any assignment could invalidate x.) (_New in 1.1_: the safe start
must precede the first `free` statement, to prevent creation of dangling
aliased pointers. Thanks Gregor!) To simplify implementation, we limit x
to a simple variable name rather than a full expression. (This too is
without loss of generality, as it is a simple matter to use a temporary
variable to store the result of a pointer expression.) Any attempt to
dereference a pointer which does not follow these rules is caught by the
static checker and disallowed.

### Runtime Support

Every pointer in the Eightebed language is implemented internally as a
structure of a machine pointer (obtained, for instance, by C's
`malloc()`) coupled with a boolean flag called `valid`. When a chunk of
memory is initially successfully allocated, `valid` is set to true.
Freeing a pointer first checks this flag; freeing the machine pointer is
only attempted if `valid` is true. In addition, just before freeing the
machine pointer, we invalidate all aliases to that pointer. (Starting
with the "root set" of the program's global variables, we traverse all
memory blocks reachable by following valid pointers from them, looking
for pointers which match the pointer about to be freed; any we find, we
set their `valid` flags to false.) After freeing a pointer, we set its
`valid` to false.

### Why this Works

Because of the static analysis, it is not possible to dereference a
pointer at a point in the program where we do not know for certain that
it is valid (i.e., it is not possible to dereference an invalid
pointer.) Because of the runtime support, as soon as a pointer becomes
invalid, all aliases of it become invalid as well. (All reachable
aliases, that is – but if an alias isn't reachable, it can't be
dereferenced anyway.) Add both of these together, and you get memory
that can leak without any risk of being reused.

And no, this isn't garbage collection, because (as stated already) we
don't care about garbage and we don't collect anything. Yes, the runtime
support looks a bit like the mark phase of a mark-and-sweep garbage
collector, but even it has a different job: not marking everything that
is reachable, rather invalidating all aliases of a given pointer.

And finally, yes, I realize how little this proves. Long live loopholes.

    16:19:38 <Gregor> We implement this without a GC by stuffing most of a
                      GC into the free function, thereby making it just as
                      slow as a GC'd language with none of the advantages!
    16:25:29 <Gregor> So yes, although you have managed to fit my
                      requirements, I am wildly underwhelmed :P

Reference Implementation
------------------------

Cat's Eye Technologies provides a cockamamie reference implementation of
Eightebed called `8ebed2c.py`. Written in Python 2.7 or 3.6, it compiles
Eightebed code to C, and for convenience will optionally compile that C
with the C compiler of your choice and run the resulting executable.

`8ebed2c.py` ships with a fairly extensive (for a language like this!)
suite of test programs, which can of course double as example sources;
these can be found in the `eightebed.tests` module.

`8ebed2c.py` also ships with a parser combinator module called `rooibos.py`
which, being a single file and in the public domain, can be dropped into
and used in any Python project that requires an LL(1) recursive-descent
parser, if that's your sort of thing.

For an appreciation of just how cockamamie `8ebed2c.py` is, run
`8ebed2c.py --help` and read through the command-line options it
provides.

Legal Issues
------------

The name Eightebed started life as a typo for the word "enlightened"
made on an iPhone by a mysterious individual known only as Alise. (Well,
perhaps not *only*.) Alise has aggressively asserted her intellectual
property rights by copyrighting [*sic*] the name Eightebed. Cat's Eye
Technologies has pursued permission to use the name for this language,
only to be told that the procedure for obtaining such permission
"involves five yaks, a Golden toad that hasn't eaten for five days, five
boxes of antique confetti (not stripped of uranium), dye number 90
(blood green), a very confused weasel, and three pieces of A4.15 paper."

Cat's Eye Technologies' legal-and-yak-husbandry team is currently
investigating the feasibility of this arrangement, and as of this
writing, official permission is still pending. If complications persist,
another, less contentious name (such as "Microsoft Windows 7") may need
to be chosen for this language.

    17:52:08 <alise> cpressey: I request that all harm is done to animals
                     in the making of this production.

Future Work
-----------

*In which we reveal the outline of a grand plan for a blockbuster sequel
to Eightebed which will never materialize*

-   To be titled _Eightebed: Ascension_ or _Eightebed: Generations_. At
    least, title should have one of those bad-ass colons in it. Possibly
    _Eightebed: Eightebed_.
-   To support functions, analysis of arbitrary expressions as the
    condition in an `if valid`, pointers to unnamed types, structures
    which contain other structures, and all that other boring stuff that
    we just said doesn't matter.
-   To have a literate specification written in SUPER ITALIAN, thus
    giving all programs the power of UNMATCHED PROPHETIC SNEEZING.
-   To be co-authored with Frank Zappa (note: turns out Mr. Zappa is
    dead. Maybe Tipper Gore instead? Yes, that should work.)
-   ~~To include a garbage collector.~~
-   Puppets???

Happy leaking!  
Chris Pressey  
September 1, 2010  
Evanston, IL
