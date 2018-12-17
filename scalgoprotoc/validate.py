# -*- mode: python; tab-width: 4; indent-tabs-mode: t; python-indent-offset: 4; coding: utf-8 -*-
"""
Validate a schema
"""
from .annotate import annotate
from .parser import ParseError, Parser


def run(args) -> int:
    data = open(args.schema).read()
    p = Parser(data)
    try:
        ast = p.parse_document()
        if annotate(data, ast):
            print("Schema is valid")
            return 0
    except ParseError as err:
        err.describe(data)
    return 1


def setup(subparsers) -> None:
    cmd = subparsers.add_parser("validate", help="Validate schema")
    cmd.add_argument("schema", help="schema to validate")
    cmd.set_defaults(func=run)