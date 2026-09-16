from apps.exercises.data.python_foundations.builders import (
    CREATE,
    FIX,
    code,
    code_function,
    code_stdout,
    fill_gap,
    mcq,
)

SKILL = "debugging"

ZERO_DIVISION_TRACEBACK = code(
    """
    Traceback (most recent call last):
      File "orders.py", line 6, in <module>
        print(unit_price(total, quantity))
      File "orders.py", line 2, in unit_price
        return total / quantity
    ZeroDivisionError: division by zero
    """
)

LESSONS = {
    ("syntax-errors", "code-python-cannot-read"): [
        mcq(
            "spot-the-syntax-error",
            "Which line won't parse?",
            "Which of these lines causes a SyntaxError?",
            options=[
                "if total > 10",
                "print(total)",
                "total = total + 1",
                'names = ["a", "b"]',
            ],
            correct="a",
            explanation="An if statement needs a colon at the end of the line.",
            seconds=25,
            misconceptions=("error-kinds",),
        ),
        code_stdout(
            "unclosed-bracket",
            "An unclosed bracket",
            "The program should print 2, but Python can't read it. Fix it.",
            mode=FIX,
            seconds=60,
            starter="""
                items = ["pen", "book"
                print(len(items))
            """,
            solution="""
                items = ["pen", "book"]
                print(len(items))
            """,
            expected="2\n",
            misconceptions=("syntax-unclosed-bracket",),
        ),
    ],
    ("runtime-errors", "when-running-code-fails"): [
        mcq(
            "missing-key-error",
            "Name the error",
            "Which error does this program raise?",
            snippet="""
                ages = {"ana": 31}
                print(ages["ben"])
            """,
            options=["SyntaxError", "KeyError", "IndexError", "NameError"],
            correct="b",
            explanation="The code is valid, but at run time the dictionary has no key 'ben'.",
            seconds=30,
            misconceptions=("error-kinds",),
        ),
        code_stdout(
            "join-text-and-number",
            "Text plus a number",
            "The program should print You have <points> points, but it crashes with TypeError. "
            "Fix it.",
            mode=FIX,
            seconds=70,
            instructions="The program is run with different numbers as input.",
            starter="""
                points = int(input())
                print("You have " + points + " points")
            """,
            solution="""
                points = int(input())
                print("You have " + str(points) + " points")
            """,
            tests=[("5\n", "You have 5 points\n"), ("12\n", "You have 12 points\n")],
            misconceptions=("type-mismatch",),
        ),
    ],
    ("logic-errors", "wrong-answers-no-errors"): [
        mcq(
            "name-the-error-kind",
            "No error message",
            "A program runs to the end without any error message, but prints the wrong total. "
            "What kind of error is this?",
            options=["A syntax error", "A runtime error", "A logic error", "An import error"],
            correct="c",
            explanation="Logic errors don't stop the program; you find them by comparing the "
            "actual result with the expected one.",
            seconds=25,
            misconceptions=("error-kinds",),
        ),
        fill_gap(
            "count-the-passes",
            "Count the passes",
            "A score of 50 or more is a pass. Complete the condition so passed counts correctly.",
            template="""
                passed = 0
                for score in scores:
                    if score __ 50:
                        passed = passed + 1
            """,
            answers=[">="],
            seconds=40,
            misconceptions=("comparison-boundary",),
        ),
        code_function(
            "count-up-off-by-one",
            "One number short",
            "count_up_to(n) should return [1, 2, ..., n], but the last number is always "
            "missing. Fix it.",
            mode=FIX,
            seconds=75,
            function_name="count_up_to",
            starter="""
                def count_up_to(n):
                    return list(range(1, n))
            """,
            solution="""
                def count_up_to(n):
                    return list(range(1, n + 1))
            """,
            tests=[([3], [1, 2, 3]), ([1], [1]), ([0], []), ([5], [1, 2, 3, 4, 5])],
            misconceptions=("off-by-one", "range-exclusive-stop"),
        ),
        code_function(
            "max-without-max",
            "The largest number",
            "Write max_value(numbers) without using max(). It must also work when every number "
            "is negative. The list is never empty.",
            mode=CREATE,
            seconds=150,
            function_name="max_value",
            starter="""
                def max_value(numbers):
                    ...
            """,
            solution="""
                def max_value(numbers):
                    largest = numbers[0]
                    for number in numbers[1:]:
                        if number > largest:
                            largest = number
                    return largest
            """,
            tests=[
                ([[3, 9, 2]], 9),
                ([[-5, -2, -9]], -2),
                ([[7]], 7),
                ([[0, -1]], 0),
            ],
            misconceptions=("initial-value",),
        ),
    ],
    ("tracebacks", "reading-a-traceback"): [
        mcq(
            "where-to-fix",
            "Where is the problem?",
            "Read the traceback. Which line needs fixing?",
            snippet="""
                Traceback (most recent call last):
                  File "shop.py", line 7, in <module>
                    total = add_tax(price)
                  File "shop.py", line 3, in add_tax
                    return price * rate
                NameError: name 'rate' is not defined
            """,
            options=[
                "Line 7, because that is where the program called add_tax",
                "Line 3, inside add_tax, where rate is used but was never defined",
                "The first line of the traceback",
                "None: tracebacks are often wrong",
            ],
            correct="b",
            explanation="The last lines show where the error actually happened and why.",
            seconds=50,
            misconceptions=("reading-traceback",),
        ),
        fill_gap(
            "read-from-the-bottom",
            "Where to start reading",
            "Complete the tip about reading tracebacks.",
            template="Read a traceback from the __ up: the error type and message are there.",
            answers=["bottom"],
            case_sensitive=False,
            seconds=30,
            misconceptions=("reading-traceback",),
        ),
        code_stdout(
            "zero-quantity-orders",
            "Fix the cause",
            "The traceback ends with ZeroDivisionError. Fix the cause, not the symptom: an order "
            "with quantity 0 should print no items instead of crashing.",
            mode=FIX,
            seconds=150,
            starter="""
                def unit_price(total, quantity):
                    return total / quantity

                orders = [(10, 2), (9, 0), (8, 4)]
                for total, quantity in orders:
                    print(unit_price(total, quantity))
            """,
            solution="""
                def unit_price(total, quantity):
                    return total / quantity

                orders = [(10, 2), (9, 0), (8, 4)]
                for total, quantity in orders:
                    if quantity == 0:
                        print("no items")
                    else:
                        print(unit_price(total, quantity))
            """,
            expected="5.0\nno items\n2.0\n",
            extra_content={"traceback": ZERO_DIVISION_TRACEBACK},
            misconceptions=("reading-traceback", "symptom-vs-cause"),
        ),
    ],
    ("debugging-workflow", "a-debugging-routine"): [
        mcq(
            "first-debugging-step",
            "Where to begin",
            "A function returns the wrong value. What is the best first step?",
            options=[
                "Rewrite the whole function from scratch",
                "Reproduce the problem with a small input whose correct answer you know",
                "Wrap the code in try/except so the problem goes away",
                "Change lines one at a time until the output looks right",
            ],
            correct="b",
            explanation="A small, known case lets you compare actual and expected results and "
            "narrow down the cause.",
            seconds=35,
            misconceptions=("debugging-process",),
        ),
        fill_gap(
            "debug-print-total",
            "Watch the running total",
            "Complete the debug print so it shows the running total at each step.",
            template="""
                def total_price(prices):
                    total = 0
                    for price in prices:
                        print("DEBUG price =", price, "total =", __)
                        total = total + price
                    return total
            """,
            answers=["total"],
            seconds=35,
            misconceptions=("debugging-process",),
        ),
    ],
    ("debugging-workflow", "fix-the-broken-program"): [
        code_function(
            "count-passes-two-bugs",
            "Two bugs, one function",
            "count_passes(scores, pass_mark) should count scores at or above the pass mark. It "
            "always returns 0 and has a second, hidden bug. Find and fix both.",
            mode=FIX,
            seconds=180,
            function_name="count_passes",
            starter="""
                def count_passes(scores, pass_mark):
                    passes = 0
                    for score in scores:
                        if score > pass_mark:
                            passes + 1
                    return passes
            """,
            solution="""
                def count_passes(scores, pass_mark):
                    passes = 0
                    for score in scores:
                        if score >= pass_mark:
                            passes = passes + 1
                    return passes
            """,
            tests=[
                ([[50, 49, 70], 50], 2),
                ([[], 50], 0),
                ([[10, 20], 5], 2),
                ([[5], 5], 1),
            ],
            misconceptions=("expression-not-assigned", "comparison-boundary"),
        ),
        code_function(
            "safe-divide",
            "Divide safely",
            "Write safe_divide(a, b) that returns a / b, or None when b is 0 instead of crashing.",
            mode=CREATE,
            seconds=100,
            function_name="safe_divide",
            starter="""
                def safe_divide(a, b):
                    ...
            """,
            solution="""
                def safe_divide(a, b):
                    if b == 0:
                        return None
                    return a / b
            """,
            tests=[([10, 2], 5.0), ([1, 0], None), ([0, 5], 0.0), ([-9, 3], -3.0)],
            misconceptions=("symptom-vs-cause",),
        ),
    ],
}
