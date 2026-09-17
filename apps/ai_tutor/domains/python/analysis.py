"""Deterministic static facts about learner Python source.

Parsing only (``ast.parse``): nothing is compiled for execution, evaluated or imported.
Learner code runs exclusively in ``apps.python_runner``. Error messages and source lines are
never returned, only structural facts and positions.
"""

import ast

MAX_SOURCE_CHARS = 65_536
SYNTAX_ERROR_TYPES = ("TabError", "IndentationError", "SyntaxError")


def _counts(tree: ast.AST) -> dict:
    nodes = list(ast.walk(tree))

    def count(*types) -> int:
        return sum(1 for node in nodes if isinstance(node, types))

    calls = [
        node.func.id
        for node in nodes
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
    ]
    loops = count(ast.For, ast.AsyncFor, ast.While)
    functions = count(ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)
    returns = count(ast.Return)
    ifs = count(ast.If, ast.IfExp)
    return {
        "has_if": ifs > 0,
        "has_for": count(ast.For, ast.AsyncFor, ast.comprehension) > 0,
        "has_while": count(ast.While) > 0,
        "has_function": functions > 0,
        "has_return": returns > 0,
        "has_print": "print" in calls,
        "has_range": "range" in calls,
        "has_class": count(ast.ClassDef) > 0,
        "if_count": ifs,
        "loop_count": loops,
        "function_count": functions,
        "return_count": returns,
    }


def analyze_source(source: object) -> dict:
    """Compact structural facts, or syntax-error position, for one submission."""
    if not isinstance(source, str) or not source.strip():
        return {"analysed": False, "reason": "no_source"}
    if len(source) > MAX_SOURCE_CHARS:
        return {"analysed": False, "reason": "source_too_large"}
    try:
        tree = ast.parse(source)
    except SyntaxError as exc:  # includes IndentationError and TabError
        error_type = type(exc).__name__
        return {
            "analysed": True,
            "syntax_valid": False,
            "error_type": error_type if error_type in SYNTAX_ERROR_TYPES else "SyntaxError",
            "line": exc.lineno if isinstance(exc.lineno, int) else None,
            "offset": exc.offset if isinstance(exc.offset, int) else None,
        }
    except (ValueError, RecursionError, MemoryError):
        return {"analysed": False, "reason": "unparseable"}
    return {"analysed": True, "syntax_valid": True, **_counts(tree)}
