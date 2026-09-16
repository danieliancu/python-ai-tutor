from apps.exercises.data.python_foundations.builders import (
    CREATE,
    FIX,
    code_function,
    code_stdout,
    fill_gap,
    mcq,
)

SKILL = "decisions"

LESSONS = {
    ("booleans", "true-and-false"): [
        mcq(
            "which-value-is-truthy",
            "Truthy or falsy?",
            "Which of these values counts as true in an if statement?",
            options=[
                "0",
                '"" (an empty string)',
                "[] (an empty list)",
                '"0" (a string with a zero)',
            ],
            correct="d",
            explanation="Zero and empty collections are falsy. Any non-empty string is truthy, "
            'even "0".',
            seconds=35,
            misconceptions=("truthiness",),
        ),
        code_function(
            "is-empty-text",
            "Is the text empty?",
            "Write is_empty(text) that returns True when the string is empty, otherwise False.",
            mode=CREATE,
            seconds=90,
            function_name="is_empty",
            starter="""
                def is_empty(text):
                    ...
            """,
            solution="""
                def is_empty(text):
                    return len(text) == 0
            """,
            tests=[([""], True), (["a"], False), ([" "], False), (["False"], False)],
            misconceptions=("truthiness",),
        ),
    ],
    ("comparison-operators", "comparing-values"): [
        mcq(
            "ten-or-more",
            "Ten or more",
            "Which condition is True exactly when value is 10 or more?",
            options=["value > 10", "value >= 10", "value < 10", "value <= 10"],
            correct="b",
            explanation=">= includes 10 itself; > would leave 10 out.",
            seconds=25,
            misconceptions=("comparison-boundary", "comparison-direction"),
        ),
        fill_gap(
            "below-thirteen",
            "Children's ticket",
            "is_child must be True when age is below 13. Complete the comparison.",
            template="is_child = age __ 13",
            answers=["<"],
            explanation="< is strictly less than, so 13 itself is not a child's age.",
            seconds=30,
            misconceptions=("comparison-direction", "comparison-boundary"),
        ),
    ],
    ("comparison-operators", "inclusive-or-exclusive"): [
        code_function(
            "voting-age-boundary",
            "Old enough to vote",
            "can_vote(age) should return True for people aged 18 or older. It gives the wrong "
            "answer for someone who is exactly 18. Fix it.",
            mode=FIX,
            seconds=75,
            function_name="can_vote",
            starter="""
                def can_vote(age):
                    return age > 18
            """,
            solution="""
                def can_vote(age):
                    return age >= 18
            """,
            tests=[([18], True), ([17], False), ([30], True), ([0], False)],
            misconceptions=("comparison-boundary",),
        ),
        code_function(
            "value-in-range",
            "Inside the range",
            "Write in_range(value, low, high) that returns True when value is between low and "
            "high, including both ends.",
            mode=CREATE,
            seconds=100,
            function_name="in_range",
            starter="""
                def in_range(value, low, high):
                    ...
            """,
            solution="""
                def in_range(value, low, high):
                    return low <= value <= high
            """,
            tests=[
                ([5, 1, 10], True),
                ([1, 1, 10], True),
                ([10, 1, 10], True),
                ([0, 1, 10], False),
                ([11, 1, 10], False),
            ],
            misconceptions=("comparison-boundary",),
        ),
    ],
    ("if-statements", "making-a-decision"): [
        mcq(
            "what-the-if-controls",
            "What does the if control?",
            "What does this program print?",
            snippet="""
                temperature = 30
                if temperature > 25:
                    print("Hot")
                print("Done")
            """,
            options=["Hot only", "Hot, then Done", "Done only", "Nothing"],
            correct="b",
            explanation='Only the indented line belongs to the if. print("Done") always runs.',
            seconds=30,
            misconceptions=("indentation-block",),
        ),
        fill_gap(
            "free-shipping-threshold",
            "Free shipping",
            "Print Free shipping when the order total is at least 50.",
            template="""
                if total __ 50:
                    print("Free shipping")
            """,
            answers=[">="],
            explanation='"At least 50" includes 50, so use >=.',
            seconds=35,
            misconceptions=("comparison-boundary",),
        ),
        code_stdout(
            "indent-the-branch",
            "Missing indentation",
            "The program should print Access granted, but Python refuses to run it. Fix it.",
            mode=FIX,
            seconds=60,
            starter="""
                password = "open sesame"
                if password == "open sesame":
                print("Access granted")
            """,
            solution="""
                password = "open sesame"
                if password == "open sesame":
                    print("Access granted")
            """,
            expected="Access granted\n",
            misconceptions=("indentation-block",),
        ),
        code_function(
            "describe-temperature",
            "Freezing or not",
            "Write describe_temperature(celsius) that returns 'freezing' when the temperature is "
            "below 0, otherwise 'not freezing'.",
            mode=CREATE,
            seconds=90,
            function_name="describe_temperature",
            starter="""
                def describe_temperature(celsius):
                    ...
            """,
            solution="""
                def describe_temperature(celsius):
                    if celsius < 0:
                        return "freezing"
                    return "not freezing"
            """,
            tests=[
                ([-5], "freezing"),
                ([0], "not freezing"),
                ([12], "not freezing"),
                ([-0.5], "freezing"),
            ],
            misconceptions=("comparison-boundary",),
        ),
    ],
    ("elif-and-else", "choosing-between-branches"): [
        mcq(
            "first-true-branch-wins",
            "Which branch runs?",
            "What does this program print?",
            snippet="""
                score = 85
                if score >= 50:
                    print("Pass")
                elif score >= 80:
                    print("Merit")
                else:
                    print("Fail")
            """,
            options=["Pass", "Merit", "Pass, then Merit", "Fail"],
            correct="a",
            explanation="Python runs only the first branch whose condition is true; "
            "score >= 50 is checked first.",
            seconds=40,
            misconceptions=("elif-order",),
        ),
        code_function(
            "grade-branch-order",
            "Merit never happens",
            "grade(score) should return 'merit' for 80 or more, 'pass' for 50 to 79 and 'fail' "
            "below 50. Nobody ever gets a merit. Fix it.",
            mode=FIX,
            seconds=90,
            function_name="grade",
            starter="""
                def grade(score):
                    if score >= 50:
                        return "pass"
                    elif score >= 80:
                        return "merit"
                    else:
                        return "fail"
            """,
            solution="""
                def grade(score):
                    if score >= 80:
                        return "merit"
                    elif score >= 50:
                        return "pass"
                    else:
                        return "fail"
            """,
            tests=[
                ([85], "merit"),
                ([80], "merit"),
                ([79], "pass"),
                ([50], "pass"),
                ([49], "fail"),
            ],
            misconceptions=("elif-order",),
        ),
        code_function(
            "ticket-price",
            "Ticket prices",
            "Write ticket_price(age): children under 12 pay 5, people aged 65 and over pay 7, "
            "and everyone else pays 10.",
            mode=CREATE,
            seconds=120,
            function_name="ticket_price",
            starter="""
                def ticket_price(age):
                    ...
            """,
            solution="""
                def ticket_price(age):
                    if age < 12:
                        return 5
                    elif age >= 65:
                        return 7
                    else:
                        return 10
            """,
            tests=[([5], 5), ([11], 5), ([12], 10), ([64], 10), ([65], 7), ([80], 7)],
            misconceptions=("comparison-boundary",),
        ),
    ],
    ("logical-operators", "combining-conditions"): [
        fill_gap(
            "adult-with-ticket",
            "Both conditions",
            "Allow entry only when the visitor is at least 18 and has a ticket.",
            template="""
                if age >= 18 __ has_ticket:
                    print("Welcome")
            """,
            answers=["and"],
            seconds=30,
        ),
        mcq(
            "weekend-condition",
            "Is it the weekend?",
            'Which expression is True exactly when day is "Saturday" or "Sunday"?',
            options=[
                'day == "Saturday" or "Sunday"',
                'day == "Saturday" or day == "Sunday"',
                'day == "Saturday" and day == "Sunday"',
                'day == ("Saturday" or "Sunday")',
            ],
            correct="b",
            explanation='Each side of or must be a full comparison. "Sunday" on its own is '
            "always truthy, so option a is always True.",
            seconds=50,
            misconceptions=("or-comparison",),
        ),
    ],
}
