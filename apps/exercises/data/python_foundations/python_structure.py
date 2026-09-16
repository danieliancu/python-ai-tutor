from apps.exercises.data.python_foundations.builders import (
    CREATE,
    FIX,
    code_stdout,
    fill_gap,
    mcq,
)

SKILL = "python-structure"

LESSONS = {
    ("imports", "using-the-standard-library"): [
        fill_gap(
            "import-sqrt",
            "Import one function",
            "Complete the import so the program prints 7.0.",
            template="""
                from math import __
                print(sqrt(49))
            """,
            answers=["sqrt"],
            seconds=30,
        ),
        code_stdout(
            "pi-and-ceiling",
            "Using the math module",
            "Import the math module, then print pi rounded to 2 decimal places and, on the next "
            "line, 7 / 2 rounded up to a whole number.",
            mode=CREATE,
            seconds=100,
            starter="# Import math, then print the two values",
            solution="""
                import math

                print(round(math.pi, 2))
                print(math.ceil(7 / 2))
            """,
            expected="3.14\n4\n",
        ),
    ],
    ("modules", "your-own-modules"): [
        mcq(
            "use-own-module",
            "Use your own module",
            "helpers.py (next to main.py) defines def slugify(text). Which code in main.py "
            "calls it correctly?",
            options=[
                'import helpers, then helpers.slugify("Hi there")',
                "import helpers.py",
                "from helpers import slugify()",
                "include helpers",
            ],
            correct="a",
            explanation="Import the module by name (without .py) and call functions through it.",
            seconds=40,
            misconceptions=("import-syntax",),
        ),
        fill_gap(
            "import-just-greet",
            "Import one name",
            "main.py should import only the greet function from greetings.py.",
            template="from greetings __ greet",
            answers=["import"],
            seconds=30,
        ),
    ],
    ("packages", "grouping-modules"): [
        mcq(
            "import-from-package",
            "Import from a package",
            "The project has shop/__init__.py and shop/cart.py, which defines add_item. From a "
            "script next to the shop folder, which import works?",
            options=[
                "from shop.cart import add_item",
                "from shop/cart import add_item",
                "import cart from shop",
                "from cart.shop import add_item",
            ],
            correct="a",
            explanation="Packages use dotted paths: package.module.",
            seconds=40,
            misconceptions=("import-syntax",),
        ),
        fill_gap(
            "dotted-module-path",
            "The dotted path",
            "The package is shop, the module is pricing and the function is apply_discount. "
            "Complete the import.",
            template="from __ import apply_discount",
            answers=["shop.pricing"],
            seconds=35,
            misconceptions=("import-syntax",),
        ),
    ],
    ("main-guard", "script-or-module"): [
        code_stdout(
            "main-guard-typo",
            "The script that never runs",
            "Run directly, this file should print Hello, Ana! but prints nothing. Fix the guard.",
            mode=FIX,
            seconds=60,
            starter="""
                def greet(name):
                    return f"Hello, {name}!"

                if __name__ == "main":
                    print(greet("Ana"))
            """,
            solution="""
                def greet(name):
                    return f"Hello, {name}!"

                if __name__ == "__main__":
                    print(greet("Ana"))
            """,
            expected="Hello, Ana!\n",
            misconceptions=("main-guard",),
        ),
        code_stdout(
            "report-main-function",
            "A proper entry point",
            "Write a main() function that prints Report ready, and call it only when the file "
            "is run directly.",
            mode=CREATE,
            seconds=90,
            instructions='Use if __name__ == "__main__": to call main(). Your printed output is '
            "checked.",
            starter="# Define main(), then add the guard",
            solution="""
                def main():
                    print("Report ready")


                if __name__ == "__main__":
                    main()
            """,
            expected="Report ready\n",
            misconceptions=("main-guard",),
        ),
    ],
}
