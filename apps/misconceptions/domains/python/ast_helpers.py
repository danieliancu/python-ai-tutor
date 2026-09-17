"""Static analysis of Python source. Parsing only: nothing here compiles or runs code.

Learner code is executed exclusively by the isolated runner (``apps.python_runner``).
"""

import ast
import copy
from collections.abc import Callable

MAX_SOURCE_CHARS = 65_536

COMPARISON_OPS = {
    ast.Lt: ("lt", False),
    ast.LtE: ("lt", True),
    ast.Gt: ("gt", False),
    ast.GtE: ("gt", True),
}


def parse(source: object) -> ast.Module | None:
    """The syntax tree, or None for anything that isn't small, valid Python text."""
    if not isinstance(source, str) or len(source) > MAX_SOURCE_CHARS:
        return None
    try:
        return ast.parse(source)
    except (SyntaxError, ValueError, RecursionError, MemoryError):
        return None


class _Placeholder(ast.AST):
    _fields = ()


def masked_dump(tree: ast.AST, mask: Callable[[ast.AST], ast.AST | None]) -> str:
    """``ast.dump`` of a copy where ``mask`` may replace nodes (it returns None to keep one)."""

    class Masker(ast.NodeTransformer):
        def visit(self, node):
            replacement = mask(node)
            if replacement is not None:
                return replacement
            return self.generic_visit(node)

    return ast.dump(Masker().visit(copy.deepcopy(tree)))


def _walk(tree: ast.AST) -> list[ast.AST]:
    """Nodes in a deterministic depth-first source order."""
    nodes = []

    def visit(node: ast.AST) -> None:
        nodes.append(node)
        for child in ast.iter_child_nodes(node):
            visit(child)

    visit(tree)
    return nodes


def comparison_ops(tree: ast.AST) -> list[ast.cmpop]:
    return [op for node in _walk(tree) if isinstance(node, ast.Compare) for op in node.ops]


def mask_comparison_ops(node: ast.AST) -> ast.AST | None:
    if isinstance(node, ast.cmpop):
        return _Placeholder()
    return None


def is_range_call(node: ast.AST) -> bool:
    return (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "range"
        and not node.keywords
    )


def range_calls(tree: ast.AST) -> list[ast.Call]:
    return [node for node in _walk(tree) if is_range_call(node)]


def mask_range_arguments(node: ast.AST) -> ast.AST | None:
    if is_range_call(node):
        return ast.Call(func=ast.Name(id="range", ctx=ast.Load()), args=[], keywords=[])
    return None


def loop_jumps(tree: ast.AST) -> list[ast.stmt]:
    return [node for node in _walk(tree) if isinstance(node, ast.Break | ast.Continue)]


def mask_loop_jumps(node: ast.AST) -> ast.AST | None:
    if isinstance(node, ast.Break | ast.Continue):
        return ast.Pass()
    return None


def has_while(tree: ast.AST) -> bool:
    return any(isinstance(node, ast.While) for node in _walk(tree))


def same_node(a: ast.AST, b: ast.AST) -> bool:
    return ast.dump(a) == ast.dump(b)


def int_value(node: ast.AST) -> int | None:
    """The value of a plain (optionally negated) integer literal."""
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.USub | ast.UAdd):
        inner = int_value(node.operand)
        if inner is None:
            return None
        return -inner if isinstance(node.op, ast.USub) else inner
    if isinstance(node, ast.Constant) and type(node.value) is int:
        return node.value
    return None


def plus_one_base(node: ast.AST) -> ast.AST | None:
    """``X`` when ``node`` is ``X + 1``."""
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add) and int_value(node.right) == 1:
        return node.left
    return None


def sign(node: ast.AST) -> int | None:
    """-1 / +1 for an obviously negative / positive step expression, else None."""
    value = int_value(node)
    if value is not None:
        return (value > 0) - (value < 0) or None
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.USub):
        return -1
    return None
