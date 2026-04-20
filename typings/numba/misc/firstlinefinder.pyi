import ast

"""
This module provides helper functions to find the first line of a function
body.
"""

class FindDefFirstLine(ast.NodeVisitor):
    def __init__(self, name, firstlineno) -> None: ...
    def visit_FunctionDef(self, node: ast.FunctionDef):  # -> None:
        ...

def get_func_body_first_lineno(pyfunc):  # -> int | None:

    ...
