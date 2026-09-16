from apps.exercises.data.python_foundations.builders import (
    CREATE,
    FIX,
    code_function,
    code_stdout,
    fill_gap,
    mcq,
)

SKILL = "loops"

LESSONS = {
    ("for-loops", "looping-over-a-list"): [
        mcq(
            "running-total",
            "A running total",
            "What does this program print?",
            snippet="""
                total = 0
                for price in [2, 5, 3]:
                    total = total + price
                print(total)
            """,
            options=["3", "10", "2, 5 and 3 on separate lines", "0"],
            correct="b",
            explanation="The loop adds each price to total; print runs once, after the loop.",
            seconds=35,
            misconceptions=("loop-accumulator", "indentation-block"),
        ),
        fill_gap(
            "greet-every-guest",
            "Greet every guest",
            "Complete the loop so every guest is greeted by name.",
            template="""
                for name in guests:
                    print("Welcome, " + __)
            """,
            answers=["name"],
            explanation="The loop variable holds the current item on each pass.",
            seconds=30,
            misconceptions=("loop-variable",),
        ),
    ],
    ("for-loops", "filtering-while-looping"): [
        code_stdout(
            "greater-than-ten",
            "Only the big numbers",
            "Fix the program so it prints only the numbers greater than 10.",
            mode=FIX,
            seconds=60,
            starter="""
                numbers = [4, 18, 7, 25, 10, 13]
                for number in numbers:
                    if number < 10:
                        print(number)
            """,
            solution="""
                numbers = [4, 18, 7, 25, 10, 13]
                for number in numbers:
                    if number > 10:
                        print(number)
            """,
            expected="18\n25\n13\n",
            misconceptions=("comparison-direction", "comparison-boundary"),
        ),
        code_stdout(
            "long-words",
            "Long words only",
            "Print every word from the list that has more than 3 letters, one per line, in order.",
            mode=CREATE,
            seconds=100,
            starter="""
                words = ["sun", "river", "sky", "mountain", "tree"]
            """,
            solution="""
                words = ["sun", "river", "sky", "mountain", "tree"]
                for word in words:
                    if len(word) > 3:
                        print(word)
            """,
            expected="river\nmountain\ntree\n",
            misconceptions=("comparison-boundary",),
        ),
    ],
    ("range", "counting-with-range"): [
        mcq(
            "range-three",
            "What does range(3) produce?",
            "What does this program print?",
            snippet="""
                for i in range(3):
                    print(i)
            """,
            options=["1, 2, 3", "0, 1, 2", "0, 1, 2, 3", "1, 2"],
            correct="b",
            explanation="range(3) starts at 0 and stops before 3.",
            seconds=25,
            misconceptions=("range-default-start", "range-exclusive-stop"),
        ),
        fill_gap(
            "one-to-five",
            "One to five",
            "Complete the loop so it prints the numbers 1 to 5, including 5.",
            template="""
                for n in range(1, __):
                    print(n)
            """,
            answers=["6"],
            explanation="The stop value is excluded, so it must be one past the last number.",
            seconds=35,
            misconceptions=("range-exclusive-stop", "off-by-one"),
        ),
    ],
    ("range", "range-boundaries"): [
        code_stdout(
            "countdown-step",
            "Countdown",
            "The program should count down from 10 to 1 and then print Lift off!, but the loop "
            "never runs. Fix it.",
            mode=FIX,
            seconds=80,
            starter="""
                for n in range(10, 0):
                    print(n)
                print("Lift off!")
            """,
            solution="""
                for n in range(10, 0, -1):
                    print(n)
                print("Lift off!")
            """,
            expected="10\n9\n8\n7\n6\n5\n4\n3\n2\n1\nLift off!\n",
            misconceptions=("range-step",),
        ),
        code_stdout(
            "even-numbers-to-twenty",
            "Even numbers",
            "Print every even number from 2 to 20, including 20, one per line. Use range() with "
            "a step.",
            mode=CREATE,
            seconds=90,
            starter="# Use range(start, stop, step)",
            solution="""
                for n in range(2, 21, 2):
                    print(n)
            """,
            expected="".join(f"{n}\n" for n in range(2, 21, 2)),
            misconceptions=("range-exclusive-stop", "range-step", "off-by-one"),
        ),
    ],
    ("while-loops", "repeating-until-done"): [
        mcq(
            "never-ending-loop",
            "When does it stop?",
            "What happens when this program runs?",
            snippet="""
                count = 5
                while count > 0:
                    print(count)
            """,
            options=[
                "It prints 5, 4, 3, 2, 1",
                "It prints 5 once",
                "It prints 5 forever, because count never changes",
                "It prints nothing",
            ],
            correct="c",
            explanation="The condition stays true because nothing inside the loop changes count.",
            seconds=35,
            misconceptions=("infinite-while",),
        ),
        fill_gap(
            "withdraw-while-money",
            "Money left",
            "Keep withdrawing 30 while the balance is still above zero.",
            template="""
                balance = 100
                while balance __ 0:
                    balance = balance - 30
                    print(balance)
            """,
            answers=[">"],
            seconds=40,
            misconceptions=("loop-condition", "comparison-direction"),
        ),
        code_stdout(
            "count-to-five",
            "Count to five",
            "The program should print the numbers 1 to 5, but it never stops. Fix it.",
            mode=FIX,
            seconds=100,
            starter="""
                n = 1
                while n < 5:
                    print(n)
                n = n + 1
            """,
            solution="""
                n = 1
                while n <= 5:
                    print(n)
                    n = n + 1
            """,
            expected="1\n2\n3\n4\n5\n",
            misconceptions=("infinite-while", "indentation-block", "loop-condition"),
        ),
        code_function(
            "years-to-double",
            "Doubling savings",
            "Write years_to_double(amount, rate) that returns how many whole years it takes for "
            "money growing by rate percent a year to reach at least double the amount.",
            mode=CREATE,
            seconds=180,
            function_name="years_to_double",
            starter="""
                def years_to_double(amount, rate):
                    ...
            """,
            solution="""
                def years_to_double(amount, rate):
                    target = amount * 2
                    years = 0
                    while amount < target:
                        amount = amount * (1 + rate / 100)
                        years = years + 1
                    return years
            """,
            tests=[([100, 10], 8), ([100, 100], 1), ([50, 50], 2), ([100, 7], 11)],
            misconceptions=("loop-condition",),
        ),
    ],
    ("break-and-continue", "controlling-a-loop"): [
        mcq(
            "skip-and-stop",
            "Skip and stop",
            "What does this program print?",
            snippet="""
                for n in [1, 2, 3, 4, 5]:
                    if n == 3:
                        continue
                    if n == 5:
                        break
                    print(n)
            """,
            options=["1, 2", "1, 2, 4", "1, 2, 4, 5", "1, 2, 3, 4"],
            correct="b",
            explanation="continue skips 3; break ends the loop before 5 is printed.",
            seconds=45,
            misconceptions=("break-vs-continue",),
        ),
        code_function(
            "first-negative",
            "The first negative number",
            "Write first_negative(numbers) that returns the first negative number, or None if "
            "there isn't one. Stop looking as soon as you find it.",
            mode=CREATE,
            seconds=100,
            function_name="first_negative",
            starter="""
                def first_negative(numbers):
                    ...
            """,
            solution="""
                def first_negative(numbers):
                    for number in numbers:
                        if number < 0:
                            return number
                    return None
            """,
            tests=[([[3, -1, -5]], -1), ([[1, 2]], None), ([[]], None), ([[-7]], -7)],
        ),
    ],
    ("nested-loops", "loops-inside-loops"): [
        mcq(
            "count-grid-cells",
            "How many times?",
            "What does this program print?",
            snippet="""
                count = 0
                for row in range(3):
                    for col in range(4):
                        count = count + 1
                print(count)
            """,
            options=["7", "12", "3", "4"],
            correct="b",
            explanation="The inner loop runs 4 times for each of the 3 rows: 3 × 4 = 12.",
            seconds=40,
            misconceptions=("nested-loop-count",),
        ),
        fill_gap(
            "times-table-cell",
            "Times table",
            "Complete the 3 × 3 multiplication table.",
            template="""
                for row in range(1, 4):
                    line = ""
                    for col in range(1, 4):
                        line = line + str(row * __) + " "
                    print(line)
            """,
            answers=["col"],
            seconds=45,
            misconceptions=("nested-loop-variables",),
        ),
        code_stdout(
            "square-of-stars",
            "A square of stars",
            "Print a 3 × 3 square: three lines of ***. Fix the program.",
            mode=FIX,
            seconds=90,
            starter="""
                for row in range(3):
                    for col in range(3):
                        print("*", end="")
                print()
            """,
            solution="""
                for row in range(3):
                    for col in range(3):
                        print("*", end="")
                    print()
            """,
            expected="***\n***\n***\n",
            misconceptions=("nested-loop-indentation",),
        ),
        code_stdout(
            "star-triangle",
            "A triangle of stars",
            "Print a triangle with 4 rows: * then ** then *** then ****.",
            mode=CREATE,
            seconds=150,
            instructions="Use a loop inside a loop. Your printed output is checked.",
            starter="# Row 1 has one star, row 4 has four",
            solution="""
                for row in range(1, 5):
                    for star in range(row):
                        print("*", end="")
                    print()
            """,
            expected="*\n**\n***\n****\n",
            misconceptions=("nested-loop-count", "range-exclusive-stop"),
        ),
    ],
}
