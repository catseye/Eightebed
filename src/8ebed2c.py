#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""\
[python] 8ebed2c.py [-achimrtuv] [-e compiler] [-f format] [-p pedigree]
                           (in.8ebed|@testprog) (out.c|-)

8ebed2c.py: A compiler (to C) for the Eightebed programming language.
Language version 1.1.  Implementation version 2011.0510.

The @testprog syntax can be used to acquire input from the
specified attribute of the Tests class of the tests module.

Using a single hyphen for the output filename will send
the generated C source to stdout.\
"""

import logging
import sys

from optparse import OptionParser

from eightebed import tests, context, rooibos
from eightebed.drivers import parse_and_gen, compile_and_run, cmdline


logger = logging.getLogger("main")


def main(argv):
    optparser = OptionParser(__doc__)
    optparser.add_option("-a", "--dump-ast",
                         action="store_true", dest="dump_ast", default=False,
                         help="dump AST after source is parsed")
    optparser.add_option("-c", "--compile",
                         action="store_true", dest="compile", default=False,
                         help="compile generated C code")
    optparser.add_option("-e", "--c-compiler", metavar='EXECUTABLE',
                         dest="compiler", default="gcc",
                         help="specify program to use for compiling C "
                              "(default: %default)")
    optparser.add_option("-f", "--pointer-format", metavar='FORMAT',
                         dest="pointer_format", default="$%08lx",
                         help="printf format to use for pointers in "
                              "--trace-marking (default: %default)")
    optparser.add_option("-i", "--interactive",
                         action="store_true", dest="interactive",
                         default=False,
                         help="enter interactive mode")
    optparser.add_option("-m", "--trace-marking",
                         action="store_true", dest="trace_marking",
                         default=False,
                         help="trace marking actions in generated C source")
    optparser.add_option("-p", "--pedigree",
                         dest="pedigree", default=__file__,
                         help="entity to list as creator of generated C "
                         "source (default: %default)")
    optparser.add_option("-r", "--run",
                         action="store_true", dest="run", default=False,
                         help="run compiled program (implies --compile)")
    optparser.add_option("-t", "--test",
                         action="store_true", dest="test", default=False,
                         help="run test cases and exit")
    optparser.add_option("-u", "--clean",
                         action="store_true", dest="clean", default=False,
                         help="delete generated C source and executable")
    optparser.add_option("-v", "--verbose",
                         action="store_true", dest="verbose", default=False,
                         help="produce extra status output")
    (options, args) = optparser.parse_args(argv[1:])
    if options.verbose:
        logging.basicConfig(level=logging.INFO)
    if options.run:
        options.compile = True
    if options.test:
        import doctest
        (f1, smth) = doctest.testmod(rooibos)
        (f2, smth) = doctest.testmod(context)
        (f3, smth) = doctest.testmod(tests)
        if f1 + f2 + f3 == 0:
            sys.exit(0)
        else:
            sys.exit(1)
    if options.interactive:
        cmdline(options)
        sys.exit(0)
    try:
        infilename = args[0]
        outfilename = args[1]
    except IndexError:
        print "Usage:", __doc__, "\n"
        print "Run with the -h option to see a list of all options."
        sys.exit(1)
    parse_and_gen(options, infilename, outfilename, tests=tests.Tests)
    if options.compile:
        result = compile_and_run(outfilename, options)
        sys.stdout.write(result)


if __name__ == "__main__":
    main(sys.argv)
