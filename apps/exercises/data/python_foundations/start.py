from apps.exercises.data.python_foundations.builders import (
    CREATE,
    FIX,
    code_stdout,
    fill_gap,
    mcq,
)

SKILL = "start"

LESSONS = {
    ("running-python", "your-first-program"): [
        mcq(
            "top-to-bottom-order",
            "Top to bottom",
            "Python runs a file one statement at a time. In what order are the lines printed?",
            snippet="""
                print("one")
                print("two")
                print("three")
            """,
            options=[
                "three, two, one",
                "one, two, three",
                "Only three, because it is the last line",
                "All three words on a single line",
            ],
            correct="b",
            explanation="Statements run from top to bottom, and each print() ends its own line.",
            seconds=20,
            misconceptions=("execution-order",),
        ),
        code_stdout(
            "first-two-lines",
            "Your first program",
            "Write a program that prints Hello, Python! and then Ready to learn. on the next line.",
            mode=CREATE,
            seconds=90,
            starter="# Write your two print() calls below",
            solution="""
                print("Hello, Python!")
                print("Ready to learn.")
            """,
            expected="Hello, Python!\nReady to learn.\n",
        ),
    ],
    ("print-and-output", "printing-values"): [
        fill_gap(
            "print-with-separator",
            "Choose the separator",
            "Complete the call so the output is exactly 2026-09-16.",
            template='print(2026, "09", "16", sep=__)',
            answers=['"-"', "'-'"],
            explanation="sep replaces the default space placed between printed values.",
            seconds=45,
        ),
        code_stdout(
            "fix-missing-comma",
            "Print a label and a value",
            "The program should print Total: 42 but it doesn't run. Fix it.",
            mode=FIX,
            seconds=60,
            starter="""
                print("Total:" 42)
            """,
            solution="""
                print("Total:", 42)
            """,
            expected="Total: 42\n",
            misconceptions=("syntax-missing-comma",),
        ),
    ],
    ("comments", "explaining-code-with-comments"): [
        mcq(
            "what-comments-hide",
            "What does Python ignore?",
            "What does this program print?",
            snippet="""
                # print("secret")
                print("visible")  # print("hidden")
            """,
            options=[
                "visible",
                "secret, then visible",
                "visible, then hidden",
                "Nothing: the whole program is a comment",
            ],
            correct="a",
            explanation="Everything after # on a line is ignored, including code written there.",
            seconds=30,
            misconceptions=("comment-scope",),
        ),
        code_stdout(
            "restore-the-note",
            "A note that breaks the program",
            "The first line was meant as a note for humans, but it stops the program running. "
            "Fix it without deleting the note.",
            mode=FIX,
            seconds=60,
            starter="""
                Print the shopping total
                price = 4
                quantity = 3
                print(price * quantity)
            """,
            solution="""
                # Print the shopping total
                price = 4
                quantity = 3
                print(price * quantity)
            """,
            expected="12\n",
            misconceptions=("comment-syntax",),
        ),
    ],
    ("expressions", "python-as-a-calculator"): [
        mcq(
            "floor-division-and-remainder",
            "Floor division and remainder",
            "What is the value of 7 // 2 + 7 % 2?",
            options=["3.5", "4", "3", "1"],
            correct="b",
            explanation="7 // 2 is 3 (whole-number division) and 7 % 2 is 1 (the remainder).",
            seconds=40,
            misconceptions=("floor-division",),
        ),
        fill_gap(
            "average-with-parentheses",
            "Group before dividing",
            "Complete the expression so average is the mean of 4 and 8, which is 6.0.",
            template="average = __ / 2",
            answers=["(4 + 8)", "(4+8)", "(8 + 4)", "(8+4)"],
            explanation="Without parentheses, 4 + 8 / 2 divides first and gives 8.0.",
            seconds=60,
            misconceptions=("operator-precedence",),
        ),
    ],
}
