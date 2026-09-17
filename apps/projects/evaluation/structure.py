"""Structural requirements checked by parsing only. Learner code is never executed here."""

import ast
from dataclasses import dataclass

CONSTRUCT_NODES = {
    "class": (ast.ClassDef,),
    "comprehension": (ast.ListComp, ast.DictComp, ast.SetComp, ast.GeneratorExp),
    "def": (ast.FunctionDef, ast.AsyncFunctionDef),
    "dict": (ast.Dict, ast.DictComp),
    "for": (ast.For, ast.AsyncFor, ast.comprehension),
    "if": (ast.If, ast.IfExp),
    "import": (ast.Import, ast.ImportFrom),
    "list": (ast.List, ast.ListComp),
    "return": (ast.Return,),
    "try": (ast.Try, ast.TryStar),
    "while": (ast.While,),
    "with": (ast.With, ast.AsyncWith),
}


@dataclass(frozen=True)
class StructureProblem:
    reason: str
    missing: str = ""


def _calls_named(tree: ast.AST, name: str) -> bool:
    return any(
        isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == name
        for node in ast.walk(tree)
    )


def _has_main_guard(tree: ast.Module) -> bool:
    """A top-level ``if __name__ == "__main__":`` block."""
    for node in tree.body:
        test = node.test if isinstance(node, ast.If) else None
        if (
            isinstance(test, ast.Compare)
            and isinstance(test.left, ast.Name)
            and test.left.id == "__name__"
            and len(test.ops) == 1
            and isinstance(test.ops[0], ast.Eq)
            and isinstance(test.comparators[0], ast.Constant)
            and test.comparators[0].value == "__main__"
        ):
            return True
    return False


def check_structure(source: str, requires: dict | None) -> StructureProblem | None:
    """The first unmet requirement, or None. Names come from the stage's public requirements."""
    try:
        tree = ast.parse(source)
    except (SyntaxError, ValueError):
        return StructureProblem("syntax_error")
    requires = requires or {}
    functions = {
        node.name for node in tree.body if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef)
    }
    classes = {node.name: node for node in tree.body if isinstance(node, ast.ClassDef)}

    for name in requires.get("functions", []):
        if name not in functions:
            return StructureProblem("missing_function", name)
    for name in requires.get("classes", []):
        if name not in classes:
            return StructureProblem("missing_class", name)
    for qualified in requires.get("methods", []):
        class_name, method = qualified.split(".")
        node = classes.get(class_name)
        methods = {
            item.name
            for item in (node.body if node else [])
            if isinstance(item, ast.FunctionDef | ast.AsyncFunctionDef)
        }
        if method not in methods:
            return StructureProblem("missing_method", qualified)
    for construct in requires.get("constructs", []):
        if construct == "open":
            present = _calls_named(tree, "open")
        elif construct == "main_guard":
            present = _has_main_guard(tree)
        else:
            present = any(isinstance(node, CONSTRUCT_NODES[construct]) for node in ast.walk(tree))
        if not present:
            return StructureProblem("missing_construct", construct)
    return None
