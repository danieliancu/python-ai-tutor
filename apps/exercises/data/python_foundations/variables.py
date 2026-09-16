from apps.exercises.data.python_foundations.builders import (
    CREATE,
    FIX,
    code_stdout,
    fill_gap,
    mcq,
)

SKILL = "variables"

LESSONS = {
    ("variables-and-values", "storing-values"): [
        mcq(
            "trace-reassignment",
            "Trace the variable",
            "What does this program print?",
            snippet="""
                score = 5
                score = score + 2
                score = score * 2
                print(score)
            """,
            options=["10", "14", "12", "7"],
            correct="b",
            explanation="score becomes 7, then 7 * 2 = 14. Each line uses the current value.",
            seconds=35,
            misconceptions=("variable-reassignment",),
        ),
        code_stdout(
            "update-not-assigned",
            "The update that vanished",
            "The program should add 2 apples and print 5. Fix it so the variable is updated.",
            mode=FIX,
            seconds=60,
            starter="""
                apples = 3
                apples + 2
                print(apples)
            """,
            solution="""
                apples = 3
                apples = apples + 2
                print(apples)
            """,
            expected="5\n",
            misconceptions=("expression-not-assigned",),
        ),
    ],
    ("basic-types", "strings-numbers-booleans"): [
        mcq(
            "adding-strings",
            "Text or numbers?",
            "What does this program print?",
            snippet="""
                print("3" + "4")
            """,
            options=["7", "34", "An error", "3 4"],
            correct="b",
            explanation='"3" and "4" are strings, so + joins them instead of adding numbers.',
            seconds=25,
            misconceptions=("string-concatenation",),
        ),
        fill_gap(
            "division-returns-float",
            "What type does / produce?",
            "The / operator always returns a float. Complete the check so the program prints True.",
            template="print(isinstance(7 / 2, __))",
            answers=["float"],
            seconds=40,
        ),
    ],
    ("naming", "good-variable-names"): [
        mcq(
            "valid-readable-name",
            "Pick a good name",
            "Which is a valid and readable Python variable name for a user's age?",
            options=["2nd_age", "user age", "user_age", "user-age"],
            correct="c",
            explanation="Names can't start with a digit or contain spaces or hyphens; "
            "snake_case is the Python convention.",
            seconds=25,
            misconceptions=("invalid-identifier",),
        ),
        code_stdout(
            "rename-invalid-variable",
            "An invalid name",
            "This program uses an invalid variable name. Rename the variable so it prints Ana.",
            mode=FIX,
            seconds=60,
            starter="""
                1st_place = "Ana"
                print(1st_place)
            """,
            solution="""
                first_place = "Ana"
                print(first_place)
            """,
            expected="Ana\n",
            misconceptions=("invalid-identifier",),
        ),
    ],
    ("user-input", "asking-the-user"): [
        fill_gap(
            "read-a-name",
            "Ask for a name",
            "Complete the line so the program asks for the learner's name, showing Name: first.",
            template='name = __("Name: ")',
            answers=["input"],
            seconds=30,
        ),
        code_stdout(
            "welcome-to-city",
            "Welcome message",
            "Read a city name with input() and print Welcome to <city>!",
            mode=CREATE,
            seconds=90,
            instructions="Call input() without prompt text, so only your message is printed. "
            "The program is run with different cities.",
            starter="# Read the city, then print the welcome message",
            solution="""
                city = input()
                print(f"Welcome to {city}!")
            """,
            tests=[("Cluj\n", "Welcome to Cluj!\n"), ("London\n", "Welcome to London!\n")],
        ),
    ],
    ("type-conversion", "converting-types"): [
        code_stdout(
            "age-next-year",
            "Age next year",
            "The program should read an age and print the age next year, but it crashes. Fix it.",
            mode=FIX,
            seconds=75,
            instructions="The program is run with different ages as input.",
            starter="""
                age = input()
                print(age + 1)
            """,
            solution="""
                age = int(input())
                print(age + 1)
            """,
            tests=[("17\n", "18\n"), ("40\n", "41\n")],
            misconceptions=("input-returns-string",),
        ),
        mcq(
            "int-of-decimal-text",
            "Converting decimal text",
            'What happens when Python runs int("3.5")?',
            options=["It returns 3", "It returns 4", "It raises ValueError", "It returns 3.5"],
            correct="c",
            explanation="int() only accepts text that looks like a whole number; use "
            'int(float("3.5")) to get 3.',
            seconds=35,
            misconceptions=("int-conversion",),
        ),
    ],
}
