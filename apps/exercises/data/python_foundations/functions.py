from apps.exercises.data.python_foundations.builders import (
    CREATE,
    FIX,
    code_function,
    code_stdout,
    fill_gap,
    mcq,
)

SKILL = "functions"

LESSONS = {
    ("defining-and-calling-functions", "your-first-function"): [
        mcq(
            "defined-not-called",
            "Defined, but called?",
            "What does this program print?",
            snippet="""
                def greet():
                    print("Hi!")

                print("Start")
            """,
            options=["Hi!, then Start", "Start", "Start, then Hi!", "Nothing"],
            correct="b",
            explanation="def only defines the function. Its body runs when the function is "
            "called, and greet() is never called.",
            seconds=30,
            misconceptions=("definition-vs-call",),
        ),
        fill_gap(
            "call-the-menu",
            "Show the menu",
            "Add the line that calls the function so the menu is printed.",
            template="""
                def show_menu():
                    print("1. Play")
                    print("2. Quit")

                __
            """,
            answers=["show_menu()"],
            seconds=30,
            misconceptions=("definition-vs-call",),
        ),
        code_stdout(
            "call-needs-parentheses",
            "A silent goodbye",
            "The program should print Goodbye! but prints nothing. Fix it.",
            mode=FIX,
            seconds=60,
            starter="""
                def say_goodbye():
                    print("Goodbye!")

                say_goodbye
            """,
            solution="""
                def say_goodbye():
                    print("Goodbye!")

                say_goodbye()
            """,
            expected="Goodbye!\n",
            misconceptions=("definition-vs-call",),
        ),
        code_function(
            "shout",
            "Shout it",
            "Write shout(text) that returns the text in upper case followed by an exclamation "
            "mark.",
            mode=CREATE,
            seconds=90,
            function_name="shout",
            starter="""
                def shout(text):
                    ...
            """,
            solution="""
                def shout(text):
                    return text.upper() + "!"
            """,
            tests=[(["hello"], "HELLO!"), (["ok"], "OK!"), ([""], "!")],
        ),
    ],
    ("parameters", "passing-information-in"): [
        mcq(
            "parameters-vs-arguments",
            "Parameters and arguments",
            "In this program, which are the parameters and which are the arguments?",
            snippet="""
                def area(width, height):
                    return width * height

                print(area(3, 5))
            """,
            options=[
                "width and height are parameters; 3 and 5 are arguments",
                "3 and 5 are parameters; width and height are arguments",
                "All four are called parameters",
                "area is the parameter; the print() call is the argument",
            ],
            correct="a",
            explanation="Parameters are the names in the definition; arguments are the values "
            "passed in the call.",
            seconds=40,
            misconceptions=("arguments-vs-parameters",),
        ),
        code_function(
            "full-name-order",
            "Names in the wrong order",
            "full_name(first, last) should return 'Ada Lovelace' for full_name('Ada', "
            "'Lovelace'). Fix it.",
            mode=FIX,
            seconds=60,
            function_name="full_name",
            starter="""
                def full_name(first, last):
                    return last + " " + first
            """,
            solution="""
                def full_name(first, last):
                    return first + " " + last
            """,
            tests=[
                (["Ada", "Lovelace"], "Ada Lovelace"),
                ([], {"last": "Hopper", "first": "Grace"}, "Grace Hopper"),
                (["A", "B"], "A B"),
            ],
            misconceptions=("arguments-vs-parameters",),
        ),
    ],
    ("return-values", "getting-results-back"): [
        mcq(
            "print-is-not-return",
            "Printed or returned?",
            "What does this program print?",
            snippet="""
                def double(n):
                    print(n * 2)

                result = double(4)
                print(result)
            """,
            options=["8, then 8", "8, then None", "None only", "An error"],
            correct="b",
            explanation="double() prints 8 but returns nothing, so result is None.",
            seconds=40,
            misconceptions=("print-vs-return",),
        ),
        fill_gap(
            "return-the-square",
            "Send the result back",
            "Complete square(n) so that square(4) gives back 16 to the caller.",
            template="""
                def square(n):
                    __ n * n
            """,
            answers=["return"],
            seconds=30,
            misconceptions=("print-vs-return",),
        ),
        code_function(
            "adult-missing-return",
            "Missing False",
            "is_adult(age) should return True for 18 and over and False otherwise. For "
            "younger people it returns None. Fix it.",
            mode=FIX,
            seconds=75,
            function_name="is_adult",
            starter="""
                def is_adult(age):
                    if age >= 18:
                        return True
            """,
            solution="""
                def is_adult(age):
                    return age >= 18
            """,
            tests=[([20], True), ([18], True), ([17], False), ([0], False)],
            misconceptions=("missing-return",),
        ),
        code_function(
            "average-of-list",
            "Average",
            "Write average(numbers) that returns the mean of the numbers, or 0 for an empty list.",
            mode=CREATE,
            seconds=110,
            function_name="average",
            starter="""
                def average(numbers):
                    ...
            """,
            solution="""
                def average(numbers):
                    if not numbers:
                        return 0
                    return sum(numbers) / len(numbers)
            """,
            tests=[([[2, 4, 6]], 4), ([[5]], 5), ([[]], 0), ([[1, 2]], 1.5)],
            misconceptions=("print-vs-return",),
        ),
    ],
    ("scope", "local-and-global-names"): [
        mcq(
            "local-assignment",
            "Did the reset work?",
            "What does this program print?",
            snippet="""
                count = 10

                def reset():
                    count = 0

                reset()
                print(count)
            """,
            options=["0", "10", "None", "An error"],
            correct="b",
            explanation="Assigning inside reset() creates a separate local variable; the "
            "global count is unchanged.",
            seconds=45,
            misconceptions=("local-scope",),
        ),
        fill_gap(
            "pass-the-rate",
            "Pass it in",
            "Pass the tax rate into the function as an argument instead of relying on a global "
            "inside it.",
            template="""
                tax_rate = 0.2

                def price_with_tax(price, rate):
                    return price * (1 + rate)

                print(price_with_tax(50, __))
            """,
            answers=["tax_rate", "0.2"],
            seconds=45,
            misconceptions=("local-scope",),
        ),
        code_function(
            "discount-name-error",
            "Lost inside a function",
            "final_price(price) should return the price after a 10% discount, but it crashes "
            "with NameError. Fix it.",
            mode=FIX,
            seconds=120,
            function_name="final_price",
            starter="""
                def apply_discount(price):
                    discounted = price * 0.9

                def final_price(price):
                    apply_discount(price)
                    return discounted
            """,
            solution="""
                def apply_discount(price):
                    return price * 0.9

                def final_price(price):
                    return apply_discount(price)
            """,
            tests=[([100], 90.0), ([50], 45.0), ([0], 0.0)],
            misconceptions=("local-scope", "missing-return"),
        ),
        code_function(
            "count-long-words",
            "Count long words",
            "Write count_long_words(words, min_length) that returns how many words have at "
            "least min_length letters. Use only parameters and local variables.",
            mode=CREATE,
            seconds=120,
            function_name="count_long_words",
            starter="""
                def count_long_words(words, min_length):
                    ...
            """,
            solution="""
                def count_long_words(words, min_length):
                    count = 0
                    for word in words:
                        if len(word) >= min_length:
                            count = count + 1
                    return count
            """,
            tests=[
                ([["a", "abcd", "abc"], 3], 2),
                ([[], 1], 0),
                ([["hello"], 6], 0),
                ([["hello"], 5], 1),
            ],
            misconceptions=("local-scope", "comparison-boundary"),
        ),
    ],
    ("default-arguments", "optional-parameters"): [
        mcq(
            "override-default",
            "Overriding a default",
            "What does this program print?",
            snippet="""
                def greet(name, greeting="Hello"):
                    return greeting + ", " + name

                print(greet("Ana", "Hi"))
            """,
            options=["Hello, Ana", "Hi, Ana", "Ana, Hi", "An error"],
            correct="b",
            explanation="A passed argument replaces the default value.",
            seconds=30,
            misconceptions=("default-arguments",),
        ),
        code_function(
            "mutable-default-list",
            "Tags that pile up",
            "add_tag(tag, tags) should return a list with the new tag added. Called twice "
            "without tags, the second call still contains the first tag. Fix it.",
            mode=FIX,
            seconds=150,
            function_name="add_tag",
            starter="""
                def add_tag(tag, tags=[]):
                    tags.append(tag)
                    return tags
            """,
            solution="""
                def add_tag(tag, tags=None):
                    if tags is None:
                        tags = []
                    tags.append(tag)
                    return tags
            """,
            tests=[(["a"], ["a"]), (["b"], ["b"]), (["c", ["x"]], ["x", "c"])],
            instructions="All calls run one after another in the same program.",
            same_process=True,
            misconceptions=("mutable-default",),
        ),
    ],
}
