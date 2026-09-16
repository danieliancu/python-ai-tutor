from apps.exercises.data.python_foundations.builders import (
    COMPLETE,
    CREATE,
    FIX,
    code_function,
    code_stdout,
    fill_gap,
    mcq,
)

SKILL = "real-data"

FILE_INSTRUCTIONS = (
    "The program runs in its own empty folder, so any files it creates start fresh. "
    "Your printed output is checked."
)

LESSONS = {
    ("files", "working-with-text-files"): [
        mcq(
            "append-mode",
            "Keep what's there",
            "You want to add a line to the end of log.txt without deleting what is already in "
            "it. Which mode do you open it with?",
            options=['"r"', '"w"', '"a"', '"x"'],
            correct="c",
            explanation='"a" appends. "w" empties the file first, "r" only reads and "x" fails '
            "if the file exists.",
            seconds=30,
            misconceptions=("file-modes",),
        ),
        fill_gap(
            "write-mode",
            "Start a new file",
            "Create notes.txt (replacing any old version) and write one note to it.",
            template="""
                with open("notes.txt", "__") as f:
                    f.write("Buy milk\\n")
            """,
            answers=["w"],
            seconds=35,
            misconceptions=("file-modes",),
        ),
        code_stdout(
            "diary-overwritten",
            "The disappearing diary",
            "The diary should keep both entries, but only Day 2 is printed. Fix it.",
            mode=FIX,
            seconds=90,
            instructions=FILE_INSTRUCTIONS,
            starter="""
                with open("diary.txt", "w") as f:
                    f.write("Day 1\\n")

                with open("diary.txt", "w") as f:
                    f.write("Day 2\\n")

                with open("diary.txt") as f:
                    print(f.read(), end="")
            """,
            solution="""
                with open("diary.txt", "w") as f:
                    f.write("Day 1\\n")

                with open("diary.txt", "a") as f:
                    f.write("Day 2\\n")

                with open("diary.txt") as f:
                    print(f.read(), end="")
            """,
            expected="Day 1\nDay 2\n",
            misconceptions=("file-modes",),
        ),
        code_stdout(
            "names-file-line-count",
            "Write, then read back",
            "Write the three names to names.txt, one per line. Then read the file back and "
            "print how many lines it contains.",
            mode=CREATE,
            seconds=180,
            instructions=FILE_INSTRUCTIONS,
            starter="""
                names = ["Ana", "Ben", "Cara"]
            """,
            solution="""
                names = ["Ana", "Ben", "Cara"]

                with open("names.txt", "w") as f:
                    for name in names:
                        f.write(name + "\\n")

                with open("names.txt") as f:
                    print(len(f.readlines()))
            """,
            expected="3\n",
            misconceptions=("file-modes", "newline-handling"),
        ),
    ],
    ("paths", "finding-files"): [
        mcq(
            "path-parts",
            "Parts of a path",
            "What does this program print?",
            snippet="""
                from pathlib import Path

                p = Path("reports") / "2026" / "summary.txt"
                print(p.name, p.suffix)
            """,
            options=["summary.txt .txt", "summary .txt", "reports txt", "summary.txt txt"],
            correct="a",
            explanation=".name is the final part of the path; .suffix includes the dot.",
            seconds=40,
        ),
        code_stdout(
            "read-settings-file",
            "Read the settings",
            "Complete the program: print the text stored in settings.txt, without an extra "
            "blank line at the end.",
            mode=COMPLETE,
            seconds=90,
            instructions=FILE_INSTRUCTIONS,
            starter="""
                from pathlib import Path

                settings = Path("settings.txt")
                if not settings.exists():
                    settings.write_text("theme=dark\\n")

                # Print the text inside settings.txt without an extra blank line
            """,
            solution="""
                from pathlib import Path

                settings = Path("settings.txt")
                if not settings.exists():
                    settings.write_text("theme=dark\\n")

                print(settings.read_text(), end="")
            """,
            expected="theme=dark\n",
            misconceptions=("newline-handling",),
        ),
    ],
    ("json", "structured-data-with-json"): [
        mcq(
            "parsed-json-index",
            "Inside the parsed data",
            "After this code runs, what is data['scores'][1]?",
            snippet="""
                import json

                raw = '{"name": "Ana", "scores": [7, 9]}'
                data = json.loads(raw)
            """,
            options=["9", '"9" (a string)', "[7, 9]", "An error, because data is a string"],
            correct="a",
            explanation="json.loads turns the JSON text into a dictionary, so the list holds "
            "real numbers.",
            seconds=40,
            misconceptions=("json-string-vs-data",),
        ),
        fill_gap(
            "dict-to-json-text",
            "Turn data into JSON text",
            "Complete the call so payload becomes a JSON string made from the user dictionary.",
            template="payload = json.__(user)",
            answers=["dumps"],
            explanation="dumps = dump to string; loads = load from string.",
            seconds=35,
            misconceptions=("json-string-vs-data",),
        ),
        code_stdout(
            "json-not-parsed",
            "Still just text",
            "The program should print Cluj, but it crashes with TypeError. Fix it.",
            mode=FIX,
            seconds=75,
            starter="""
                import json

                raw = '{"city": "Cluj", "population": 290000}'
                print(raw["city"])
            """,
            solution="""
                import json

                raw = '{"city": "Cluj", "population": 290000}'
                data = json.loads(raw)
                print(data["city"])
            """,
            expected="Cluj\n",
            misconceptions=("json-string-vs-data",),
        ),
        code_function(
            "total-quantity-from-json",
            "Orders in JSON",
            "Write total_quantity(json_text). The text is a JSON list of orders such as "
            '[{"item": "pen", "qty": 2}]. Return the total of all qty values.',
            mode=CREATE,
            seconds=150,
            function_name="total_quantity",
            starter="""
                import json


                def total_quantity(json_text):
                    ...
            """,
            solution="""
                import json


                def total_quantity(json_text):
                    orders = json.loads(json_text)
                    return sum(order["qty"] for order in orders)
            """,
            tests=[
                (['[{"item": "pen", "qty": 2}, {"item": "ink", "qty": 5}]'], 7),
                (["[]"], 0),
                (['[{"item": "cap", "qty": 1}]'], 1),
            ],
            misconceptions=("json-string-vs-data", "json-structure"),
        ),
    ],
    ("csv", "tables-in-csv"): [
        mcq(
            "csv-rows-and-values",
            "Rows from a CSV",
            "What does this program print?",
            snippet="""
                import csv

                lines = ["name,score", "Ana,9", "Ben,7"]
                rows = list(csv.reader(lines))
                print(len(rows), rows[1][1])
            """,
            options=["3 9", "2 7", "3 Ana", "2 9"],
            correct="a",
            explanation="The header is a row too, and each value is read as a string.",
            seconds=45,
            misconceptions=("csv-header-row", "csv-values-are-strings"),
        ),
        code_function(
            "csv-total-score",
            "Total score",
            "total_score(lines) should add up the score column of CSV lines that start with a "
            "header row, but it crashes. Fix it.",
            mode=FIX,
            seconds=150,
            function_name="total_score",
            starter="""
                import csv


                def total_score(lines):
                    total = 0
                    for row in csv.reader(lines):
                        total = total + row[1]
                    return total
            """,
            solution="""
                import csv


                def total_score(lines):
                    total = 0
                    rows = csv.reader(lines)
                    next(rows)
                    for row in rows:
                        total = total + int(row[1])
                    return total
            """,
            tests=[
                ([["name,score", "Ana,9", "Ben,7"]], 16),
                ([["name,score"]], 0),
                ([["name,score", "Cy,10"]], 10),
            ],
            misconceptions=("csv-header-row", "csv-values-are-strings"),
        ),
    ],
    ("data-transformation", "answering-questions-with-data"): [
        mcq(
            "group-totals",
            "Totals per customer",
            "What does this program print?",
            snippet="""
                orders = [
                    {"customer": "ana", "total": 20},
                    {"customer": "ben", "total": 5},
                    {"customer": "ana", "total": 15},
                ]
                totals = {}
                for order in orders:
                    name = order["customer"]
                    totals[name] = totals.get(name, 0) + order["total"]
                print(totals)
            """,
            options=[
                "{'ana': 35, 'ben': 5}",
                "{'ana': 15, 'ben': 5}",
                "{'ana': 20, 'ben': 5}",
                "A KeyError",
            ],
            correct="a",
            explanation="get() starts new customers at 0, and each order adds to that total.",
            seconds=60,
            misconceptions=("missing-key",),
        ),
    ],
    ("data-transformation", "clean-and-summarise"): [
        code_function(
            "summarise-temperatures",
            "Clean and summarise",
            "Write summarise(rows). rows are CSV lines city,temperature with a header. Skip rows "
            "whose temperature isn't a number. Return {'count': number of valid rows, "
            "'average': their average rounded to 1 decimal}, with average None when there are "
            "no valid rows.",
            mode=CREATE,
            seconds=280,
            function_name="summarise",
            starter="""
                import csv


                def summarise(rows):
                    ...
            """,
            solution="""
                import csv


                def summarise(rows):
                    temperatures = []
                    reader = csv.reader(rows)
                    next(reader)
                    for city, temperature in reader:
                        try:
                            temperatures.append(float(temperature))
                        except ValueError:
                            continue
                    if not temperatures:
                        return {"count": 0, "average": None}
                    average = sum(temperatures) / len(temperatures)
                    return {"count": len(temperatures), "average": round(average, 1)}
            """,
            tests=[
                (
                    [["city,temperature", "Cluj,21", "Iasi,n/a", "Arad,24"]],
                    {"count": 2, "average": 22.5},
                ),
                ([["city,temperature"]], {"count": 0, "average": None}),
                (
                    [["city,temperature", "Oslo,-3.5", "Rome,18.5"]],
                    {"count": 2, "average": 7.5},
                ),
            ],
            misconceptions=("csv-header-row", "csv-values-are-strings"),
        ),
    ],
}
