#!/bin/sh -x

if [ "x$PYTHON" != "x" ]; then
    if command -v "$PYTHON" > /dev/null 2>&1; then
        $PYTHON src/8ebed2c.py -t || exit 1
    else
        echo "$PYTHON not found on executable search path. Aborting."
        exit 1
    fi
else
    MISSING=""
    if command -v python2 > /dev/null 2>&1; then
        python2 src/8ebed2c.py -t || exit 1
    else
        MISSING="${MISSING}2"
    fi
    if command -v python3 > /dev/null 2>&1; then
        python3 src/8ebed2c.py -t || exit 1
    else
        MISSING="${MISSING}3"
    fi
    if [ "x${MISSING}" = "x23" ]; then
        echo "Neither python2 nor python3 found on executable search path. Aborting."
        exit 1
    fi
fi
