#!/usr/bin/python
# -*- coding: utf-8 -*-

"""
drivers.py: Drive the Eightebed compiling/C compiling/running/etc processes.
"""

import logging
import os
import sys

from pprint import pprint
from subprocess import Popen, PIPE

from eightebed.parser import parse
from eightebed.context import Context


logger = logging.getLogger("main")


def parse_and_check(program_text, options=None):
    ast = parse(program_text)
    if options is not None and options.dump_ast:
        pprint(ast)
    ast.typecheck(Context(), Context())
    ast.vanalyze(Context())
    return ast


def parse_and_gen(options, infilename, outfilename, tests=None):
    if infilename.startswith('@') and tests is not None:
        program_text = getattr(tests, infilename[1:])
    else:
        infile = open(infilename, "r")
        program_text = infile.read()
        infile.close()
    logger.info("Parsing...")
    ast = parse_and_check(program_text, options=options)
    if outfilename == '-':
        outfile = sys.stdout
    else:
        outfile = open(outfilename, "w")
    logger.info("Generating...")
    ast.emit(outfile, options)
    outfile.close()


def compile_and_run(filename, options):
    logger.info("Compiling...")
    output = Popen([options.compiler, filename], stdout=PIPE).communicate()[0]
    if options.verbose:
        sys.stdout.write(output)
    if output != '':
        raise RuntimeError, "Compilation failed!"
    if options.run:
        logger.info("Running...")
        output = Popen(["./a.out"], stdout=PIPE).communicate()[0]
    if options.clean:
        os.remove(filename)
        os.remove("./a.out")
    return output


def load_and_go(ast, options=None):
    class LoadAndGoOptions(object):
        verbose=False
        run=True
        clean=True
        compiler="gcc"
        pedigree=__file__ + ":load_and_go"
        trace_marking=False
        pointer_format="$%08lx"
    options = options or LoadAndGoOptions()
    file = open("tmp.c", "w")
    ast.emit(file, options)
    file.close()
    sys.stdout.write(compile_and_run("tmp.c", options))


def cmdline(options):
    cmd = ""
    print "Eightebed interactive!  Type 'quit' to quit."
    options.run = True
    options.clean = True
    while True:
        sys.stdout.write("> ");
        cmd = sys.stdin.readline().strip()
        if cmd == "quit":
            break
        try:
            ast = parse_and_check(cmd, options=options)
            load_and_go(ast, options)
        except Exception, e:
            print "Exception!", repr(e)
