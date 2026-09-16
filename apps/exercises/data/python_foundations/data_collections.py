from apps.exercises.data.python_foundations.builders import (
    COMPLETE,
    CREATE,
    FIX,
    code_function,
    code_stdout,
    fill_gap,
    mcq,
)

SKILL = "collections"

LESSONS = {
    ("list-basics", "your-first-list"): [
        mcq(
            "membership-is-exact",
            "Is it in the list?",
            "What does this program print?",
            snippet="""
                colours = ["red", "green", "blue"]
                print("Green" in colours)
            """,
            options=["True", "False", "An error", "green"],
            correct="b",
            explanation='in compares exactly, and "Green" is not the same string as "green".',
            seconds=30,
            misconceptions=("case-sensitive-comparison",),
        ),
        fill_gap(
            "count-the-basket",
            "How many items?",
            "Complete the line so it prints how many items are in basket.",
            template="print(__(basket))",
            answers=["len"],
            seconds=30,
        ),
        code_stdout(
            "average-hard-coded-length",
            "An average that goes stale",
            "The average is wrong once a score is added. Fix it so it stays correct when the "
            "list changes.",
            mode=FIX,
            seconds=75,
            starter="""
                scores = [7, 9, 5, 3]
                scores.append(6)
                average = sum(scores) / 4
                print(average)
            """,
            solution="""
                scores = [7, 9, 5, 3]
                scores.append(6)
                average = sum(scores) / len(scores)
                print(average)
            """,
            expected="6.0\n",
            misconceptions=("hard-coded-length",),
        ),
        code_function(
            "list-summary",
            "Summarise a list",
            "Write summary(numbers) that returns a list [smallest, largest, count].",
            mode=CREATE,
            seconds=100,
            function_name="summary",
            starter="""
                def summary(numbers):
                    ...
            """,
            solution="""
                def summary(numbers):
                    return [min(numbers), max(numbers), len(numbers)]
            """,
            tests=[
                ([[3, 1, 2]], [1, 3, 3]),
                ([[5]], [5, 5, 1]),
                ([[-2, 10, 4, 4]], [-2, 10, 4]),
            ],
        ),
    ],
    ("indexing-and-slicing", "positions-in-a-list"): [
        mcq(
            "last-letter-index",
            "The last item",
            'letters = ["a", "b", "c", "d"]. Which expression gives "d"?',
            options=["letters[4]", "letters[3]", "letters[-0]", "letters[len(letters)]"],
            correct="b",
            explanation="Indexes start at 0, so the last of 4 items is at index 3 (or -1).",
            seconds=30,
            misconceptions=("zero-based-index", "last-index"),
        ),
        fill_gap(
            "first-three-slice",
            "The first three",
            "Complete the slice so first_three holds the first three items of items.",
            template="first_three = items[__]",
            answers=[":3", "0:3"],
            explanation="The end of a slice is excluded, so :3 gives indexes 0, 1 and 2.",
            seconds=45,
            misconceptions=("slice-bounds",),
        ),
        code_stdout(
            "last-in-line",
            "Last in the queue",
            "The program should print the last person in the queue but crashes with IndexError. "
            "Fix it so it works for a queue of any length.",
            mode=FIX,
            seconds=70,
            starter="""
                queue = ["Ana", "Ben", "Cara"]
                print("Last in line:", queue[len(queue)])
            """,
            solution="""
                queue = ["Ana", "Ben", "Cara"]
                print("Last in line:", queue[-1])
            """,
            expected="Last in line: Cara\n",
            misconceptions=("last-index", "zero-based-index"),
        ),
        code_function(
            "middle-items",
            "Drop the ends",
            "Write middle(items) that returns the list without its first and last item.",
            mode=CREATE,
            seconds=90,
            function_name="middle",
            starter="""
                def middle(items):
                    ...
            """,
            solution="""
                def middle(items):
                    return items[1:-1]
            """,
            tests=[
                ([[1, 2, 3, 4]], [2, 3]),
                ([["a", "b", "c"]], ["b"]),
                ([[1, 2]], []),
                ([[]], []),
            ],
            misconceptions=("slice-bounds",),
        ),
    ],
    ("list-mutation", "changing-a-list"): [
        mcq(
            "shared-list",
            "Two names, one list",
            "What does this program print?",
            snippet="""
                a = [1, 2]
                b = a
                b.append(3)
                print(a)
            """,
            options=["[1, 2]", "[1, 2, 3]", "[3]", "An error"],
            correct="b",
            explanation="b = a does not copy the list; both names refer to the same list.",
            seconds=40,
            misconceptions=("list-aliasing",),
        ),
        code_function(
            "sorted-copy",
            "Sorted copy",
            "sorted_copy(numbers) should return a new sorted list, but it returns None. Fix it.",
            mode=FIX,
            seconds=75,
            function_name="sorted_copy",
            starter="""
                def sorted_copy(numbers):
                    result = numbers.sort()
                    return result
            """,
            solution="""
                def sorted_copy(numbers):
                    return sorted(numbers)
            """,
            tests=[([[3, 1, 2]], [1, 2, 3]), ([[]], []), ([[5, 5, 1]], [1, 5, 5])],
            misconceptions=("mutation-vs-new-list",),
        ),
    ],
    ("tuples", "fixed-groups-of-values"): [
        mcq(
            "tuples-are-immutable",
            "Changing a tuple",
            "What happens when this code runs?",
            snippet="""
                point = (3, 4)
                point[0] = 5
            """,
            options=[
                "point becomes (5, 4)",
                "A TypeError: tuples can't be changed",
                "A new tuple is created automatically",
                "point becomes (5,)",
            ],
            correct="b",
            explanation="Tuples are immutable. Build a new tuple instead, e.g. (5, point[1]).",
            seconds=30,
            misconceptions=("tuple-immutability",),
        ),
        code_stdout(
            "unpack-person",
            "Unpack a tuple",
            "Add one line that unpacks person into name, age and city so the message prints.",
            mode=COMPLETE,
            seconds=60,
            starter="""
                person = ("Ana", 31, "Cluj")
                # Unpack the tuple into name, age and city on the next line

                print(f"{name} is {age} and lives in {city}.")
            """,
            solution="""
                person = ("Ana", 31, "Cluj")
                name, age, city = person
                print(f"{name} is {age} and lives in {city}.")
            """,
            expected="Ana is 31 and lives in Cluj.\n",
        ),
    ],
    ("dictionaries", "looking-things-up"): [
        mcq(
            "get-with-default",
            "A missing key",
            "What does this program print?",
            snippet="""
                prices = {"tea": 3, "cake": 5}
                print(prices.get("coffee", 0))
            """,
            options=["A KeyError", "None", "0", "coffee"],
            correct="c",
            explanation="get() returns the default (here 0) when the key is missing.",
            seconds=30,
            misconceptions=("missing-key",),
        ),
        code_stdout(
            "missing-fruit",
            "Out of stock",
            "Print how many bananas are in stock. Fruit missing from the dictionary counts as 0.",
            mode=FIX,
            seconds=60,
            starter="""
                stock = {"apples": 4, "pears": 0}
                print(stock["bananas"])
            """,
            solution="""
                stock = {"apples": 4, "pears": 0}
                print(stock.get("bananas", 0))
            """,
            expected="0\n",
            misconceptions=("missing-key",),
        ),
        code_function(
            "add-score",
            "Keep score",
            "Write add_score(scores, name, points) that adds points to the player's total "
            "(new players start at 0) and returns the dictionary.",
            mode=CREATE,
            seconds=110,
            function_name="add_score",
            starter="""
                def add_score(scores, name, points):
                    ...
            """,
            solution="""
                def add_score(scores, name, points):
                    scores[name] = scores.get(name, 0) + points
                    return scores
            """,
            tests=[
                ([{"ana": 3}, "ana", 2], {"ana": 5}),
                ([{}, "ben", 4], {"ben": 4}),
                ([{"ana": 1}, "cara", 0], {"ana": 1, "cara": 0}),
            ],
            misconceptions=("missing-key",),
        ),
    ],
    ("sets", "unique-values"): [
        mcq(
            "set-size",
            "Unique values",
            'What does print(len({"a", "b", "a", "c", "b"})) print?',
            options=["5", "3", "2", "An error"],
            correct="b",
            explanation="A set keeps each value once, so only a, b and c remain.",
            seconds=25,
        ),
        code_function(
            "common-values",
            "In both lists",
            "Write common(a, b) that returns a sorted list of the values found in both lists, "
            "without duplicates.",
            mode=CREATE,
            seconds=100,
            function_name="common",
            starter="""
                def common(a, b):
                    ...
            """,
            solution="""
                def common(a, b):
                    return sorted(set(a) & set(b))
            """,
            tests=[
                ([[1, 2, 3], [2, 3, 4]], [2, 3]),
                ([[1], [2]], []),
                ([["x", "y", "x"], ["x"]], ["x"]),
            ],
        ),
    ],
}
