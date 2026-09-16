from apps.exercises.data.python_foundations.builders import (
    CREATE,
    FIX,
    code_function,
    code_stdout,
    fill_gap,
    mcq,
    text_rubric,
)

SKILL = "python-developer"

LESSONS = {
    ("project-planning", "planning-a-project"): [
        mcq(
            "best-decomposition",
            "Break it down",
            "You are building a tool that reads expenses from a CSV file and prints a monthly "
            "report. Which plan is best?",
            options=[
                "Write everything in one script, then test it at the end",
                "Read the rows, turn each row into a dictionary, total them by month, then "
                "format the report, checking each step as you go",
                "Start with the report layout and work out the data later",
                "Look for a finished project online and adapt it",
            ],
            correct="b",
            explanation="Small steps with clear inputs and outputs can be built and checked one "
            "at a time.",
            seconds=50,
            misconceptions=("decomposition",),
        ),
        text_rubric(
            "todo-app-plan",
            "Plan a to-do app",
            "Write a step-by-step plan (4 to 6 steps) for a command-line to-do list that can "
            "add, list and complete tasks and saves them to a JSON file.",
            mode=CREATE,
            seconds=240,
            instructions="Write one step per line. Each step should be small enough to build "
            "and check on its own.",
            criteria=[
                "Has between 4 and 6 ordered steps",
                "Separates loading/saving the JSON file from the task operations",
                "Covers adding, listing and completing tasks",
                "Says how each step will be checked (for example a small test or sample run)",
            ],
            misconceptions=("decomposition",),
        ),
    ],
    ("build-and-integration", "building-step-by-step"): [
        fill_gap(
            "reuse-the-parser",
            "Reuse the helper",
            "total() should reuse parse_line() instead of splitting lines again.",
            template="""
                def parse_line(line):
                    name, amount = line.split(",")
                    return {"name": name, "amount": float(amount)}

                def total(lines):
                    return sum(__(line)["amount"] for line in lines)
            """,
            answers=["parse_line"],
            seconds=45,
        ),
        code_function(
            "monthly-totals",
            "Monthly totals",
            "Lines look like '2026-01-15,12.5' (date, amount). Write parse_expense(line), "
            "returning the month ('2026-01') and the amount as a float, and use it in "
            "monthly_totals(lines), which returns a dictionary of month → total.",
            mode=CREATE,
            seconds=280,
            function_name="monthly_totals",
            starter="""
                def parse_expense(line):
                    ...


                def monthly_totals(lines):
                    ...
            """,
            solution="""
                def parse_expense(line):
                    date, amount = line.split(",")
                    return date[:7], float(amount)


                def monthly_totals(lines):
                    totals = {}
                    for line in lines:
                        month, amount = parse_expense(line)
                        totals[month] = totals.get(month, 0) + amount
                    return totals
            """,
            tests=[
                (
                    [["2026-01-15,12.5", "2026-01-20,7.5", "2026-02-01,3"]],
                    {"2026-01": 20.0, "2026-02": 3.0},
                ),
                ([[]], {}),
                ([["2026-03-09,1"]], {"2026-03": 1.0}),
            ],
            misconceptions=("decomposition",),
        ),
    ],
    ("testing-and-refactoring", "testing-your-code"): [
        mcq(
            "useful-test",
            "Which test catches the bug?",
            "Which test is most likely to catch an off-by-one bug in count_up_to(n)?",
            options=[
                "assert count_up_to(3) == [1, 2, 3]",
                "assert count_up_to(3) is not None",
                "assert type(count_up_to(3)) == list",
                "assert len(str(count_up_to(3))) > 0",
            ],
            correct="a",
            explanation="Only a test that checks the exact values can notice a missing or "
            "extra number.",
            seconds=45,
            misconceptions=("weak-tests", "off-by-one"),
        ),
        fill_gap(
            "expected-false",
            "Complete the test",
            "Complete the test for is_even().",
            template="""
                def test_is_even():
                    assert is_even(4) == True
                    assert is_even(7) == __
            """,
            answers=["False"],
            seconds=30,
        ),
        code_function(
            "shipping-gap",
            "The parcel with no price",
            "Testing found that a 5 kg parcel gets no price. Fix shipping_cost(weight): under 1 kg "
            "costs 3, under 5 kg costs 6, anything heavier costs 10.",
            mode=FIX,
            seconds=100,
            function_name="shipping_cost",
            starter="""
                def shipping_cost(weight):
                    if weight < 1:
                        return 3
                    if weight < 5:
                        return 6
                    if weight > 5:
                        return 10
            """,
            solution="""
                def shipping_cost(weight):
                    if weight < 1:
                        return 3
                    if weight < 5:
                        return 6
                    return 10
            """,
            tests=[([0.5], 3), ([1], 6), ([4.9], 6), ([5], 10), ([12], 10)],
            misconceptions=("comparison-boundary", "missing-return"),
        ),
        code_function(
            "refactor-receipt",
            "Refactor the receipt",
            "receipt(items, currency) repeats the same formatting three times and prints 3.5 "
            "instead of 3.50. Refactor it: write format_price(amount, currency) and use it so "
            "every line looks like 'Tea: 3.50 EUR'.",
            mode=CREATE,
            seconds=240,
            function_name="receipt",
            starter="""
                def receipt(items, currency):
                    lines = []
                    for name, price in items:
                        if currency == "EUR":
                            lines.append(name + ": " + str(round(price, 2)) + " EUR")
                        elif currency == "GBP":
                            lines.append(name + ": " + str(round(price, 2)) + " GBP")
                        else:
                            lines.append(name + ": " + str(round(price, 2)) + " " + currency)
                    return lines
            """,
            solution="""
                def format_price(amount, currency):
                    return f"{amount:.2f} {currency}"


                def receipt(items, currency):
                    return [f"{name}: {format_price(price, currency)}" for name, price in items]
            """,
            tests=[
                ([[["Tea", 3.5], ["Cake", 4]], "EUR"], ["Tea: 3.50 EUR", "Cake: 4.00 EUR"]),
                ([[], "GBP"], []),
                ([[["Pen", 0.99]], "RON"], ["Pen: 0.99 RON"]),
            ],
            misconceptions=("duplicated-code",),
        ),
    ],
    ("final-project", "project-brief"): [
        mcq(
            "first-checkpoint",
            "The first checkpoint",
            "Brief: read lines like 'Ana:9,7,8' and print each student's average and the class "
            "average. What is the best first checkpoint?",
            options=[
                "Parse one line into a name and a list of numbers, and print the result",
                "Write the final report formatting",
                "Add colours to the output",
                "Support every possible input format",
            ],
            correct="a",
            explanation="Parsing one line correctly is the foundation every later step uses.",
            seconds=45,
            misconceptions=("decomposition",),
        ),
        fill_gap(
            "split-name-and-grades",
            "Checkpoint 1: split the line",
            "Complete the checkpoint: split 'Ana:9,7,8' into the name and the grades text.",
            template="name, grades_text = line.split(__)",
            answers=['":"', "':'"],
            seconds=40,
        ),
    ],
    ("final-project", "build-your-project"): [
        code_function(
            "class-report-bugs",
            "Checkpoint 2: fix the report",
            "class_report(lines) should return each student's average (rounded to 2 decimals) "
            "and 'class_average', the average of the student averages. It crashes, and after "
            "that the class average is wrong too. Fix it.",
            mode=FIX,
            seconds=180,
            function_name="class_report",
            starter="""
                def class_report(lines):
                    report = {}
                    total = 0
                    for line in lines:
                        name, grades_text = line.split(":")
                        grades = grades_text.split(",")
                        average = sum(grades) / len(grades)
                        report[name] = round(average, 2)
                        total = average
                    report["class_average"] = round(total / len(lines), 2)
                    return report
            """,
            solution="""
                def class_report(lines):
                    report = {}
                    total = 0
                    for line in lines:
                        name, grades_text = line.split(":")
                        grades = [int(grade) for grade in grades_text.split(",")]
                        average = sum(grades) / len(grades)
                        report[name] = round(average, 2)
                        total = total + average
                    report["class_average"] = round(total / len(lines), 2)
                    return report
            """,
            tests=[
                ([["Ana:9,7,8", "Ben:6,6"]], {"Ana": 8.0, "Ben": 6.0, "class_average": 7.0}),
                ([["Cy:10"]], {"Cy": 10.0, "class_average": 10.0}),
                (
                    [["Dan:5,6", "Eve:9,10", "Fay:7"]],
                    {"Dan": 5.5, "Eve": 9.5, "Fay": 7.0, "class_average": 7.33},
                ),
            ],
            misconceptions=("csv-values-are-strings", "loop-accumulator"),
        ),
        code_stdout(
            "full-class-report",
            "Checkpoint 3: the full report",
            "Build the complete report program for the lines given in the starter code.",
            mode=CREATE,
            seconds=300,
            instructions="Print one line per student, '<name>: <average with 2 decimals>', then "
            "'Class average: <average of the student averages, 2 decimals>'.",
            starter="""
                lines = ["Ana:9,7,8", "Ben:6,6", "Cara:10,9"]

                # Build the report here
            """,
            solution="""
                lines = ["Ana:9,7,8", "Ben:6,6", "Cara:10,9"]


                def parse(line):
                    name, grades_text = line.split(":")
                    return name, [int(grade) for grade in grades_text.split(",")]


                averages = []
                for line in lines:
                    name, grades = parse(line)
                    average = sum(grades) / len(grades)
                    averages.append(average)
                    print(f"{name}: {average:.2f}")

                print(f"Class average: {sum(averages) / len(averages):.2f}")
            """,
            expected="Ana: 8.00\nBen: 6.00\nCara: 9.50\nClass average: 7.83\n",
            misconceptions=("decomposition",),
        ),
    ],
}
