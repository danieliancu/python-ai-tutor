"""The Python Foundations project pack (applied by ``manage.py seed_python_projects``).

Every stage is checked by private tests: ``driver`` code runs after the learner's program and
prints what is compared. Requirements name real curriculum concepts as "skill/concept".
"""

from textwrap import dedent

WORLD_SLUG = "python-foundations"

NO_INPUT = (
    "Don't call input() or print anything outside your functions: the checker runs your file."
)


def code(text: str) -> str:
    return dedent(text).strip("\n") + "\n"


def stage(slug, title, objective, instructions, requirements, minutes, spec, starter=""):
    return {
        "slug": slug,
        "title": title,
        "objective": objective,
        "instructions": dedent(instructions).strip(),
        "requirements": list(requirements),
        "estimated_minutes": minutes,
        "starter_code": code(starter) if starter else "",
        "evaluation_spec": spec,
    }


def driven(*checks, requires=None, fixtures=None):
    """A stdout spec where each check is (driver_code, expected_output)."""
    spec = {
        "strategy": "stdout",
        "tests": [
            {"stdin": "", "driver": code(driver), "expected_stdout": expected}
            for driver, expected in checks
        ],
    }
    if requires:
        spec["requires"] = requires
    if fixtures:
        spec["fixtures"] = fixtures
    return spec


def function_spec(name, tests, requires=None):
    spec = {
        "strategy": "function",
        "function_name": name,
        "tests": [{"args": args, "kwargs": {}, "expected": expected} for args, expected in tests],
        "run_tests_in_one_process": True,
    }
    if requires:
        spec["requires"] = requires
    return spec


TRANSACTIONS_CSV = """date,category,amount
2026-01-03,food,12.50
2026-01-04,transport,3.20
2026-01-10,food,7.25
2026-02-01,rent,500
2026-02-02,food,oops
2026-02-05,fun,15
bad line
2026-02-09,transport,4.80
"""

INVENTORY_JSON = (
    '[{"name": "pen", "price": 1.5, "quantity": 10},'
    ' {"name": "notebook", "price": 3.0, "quantity": 4},'
    ' {"name": "bag", "price": 25.0, "quantity": 1},'
    ' {"name": "broken", "price": "free"},'
    ' {"name": "ghost", "price": 2.0, "quantity": -3},'
    ' {"name": "pen", "price": 1.5, "quantity": 2}]\n'
)

STATEMENT_CSV = """date,description,amount
2026-03-01,Salary,2000
2026-03-02,Groceries,-54.20
2026-03-05,Rent,-800
2026-03-09,Cinema,-12.50
2026-03-15,Groceries,-40.30
not,a,number
2026-04-01,Salary,2000
2026-04-03,Rent,-800
2026-04-10,Groceries,-61.00
"""


NUMBER_ANALYZER = {
    "slug": "number-analyzer",
    "title": "Number Analyzer",
    "summary": "Turn a line of numbers into useful statistics and a tidy report.",
    "brief": dedent(
        """
        You'll build a small analysis tool. It takes text such as "3, 8, 12", turns it into
        a list of numbers and reports how many there are, the smallest, the largest, the
        average and how many are above 10.

        You'll use variables, conditions, lists and loops together, one step at a time.
        Each stage adds to the same program.
        """
    ).strip(),
    "order": 1,
    "difficulty": "beginner",
    "estimated_minutes": 45,
    "xp_reward": 100,
    "requirements": [
        "variables/variables-and-values",
        "decisions/if-statements",
        "collections/list-basics",
        "loops/for-loops",
    ],
    "stages": [
        stage(
            "store-numbers",
            "Store the numbers",
            "Turn comma-separated text into a list of whole numbers.",
            f"""
            Write parse_numbers(text). It splits the text on commas, strips spaces from each
            part, skips empty parts and returns the numbers as a list of ints, in order.
            For example parse_numbers("3, 8, 12") returns [3, 8, 12] and parse_numbers("")
            returns [].

            {NO_INPUT}
            """,
            ["Define parse_numbers(text)", "Use a for loop", "Return a list of ints"],
            10,
            function_spec(
                "parse_numbers",
                [
                    (["3, 8, 12"], [3, 8, 12]),
                    ([""], []),
                    ([" 5 ,, -2 "], [5, -2]),
                    (["42"], [42]),
                ],
                requires={"functions": ["parse_numbers"], "constructs": ["for"]},
            ),
            starter="""
                def parse_numbers(text):
                    # Split the text on commas and build a list of numbers.
                    return []
            """,
        ),
        stage(
            "count-and-filter",
            "Count and filter",
            "Count numbers above a limit and pick out the even ones.",
            """
            Add two functions and keep parse_numbers:
            - count_above(numbers, limit) returns how many numbers are greater than limit.
            - evens(numbers) returns a new list with only the even numbers, in order.
            """,
            ["Keep parse_numbers", "Define count_above(numbers, limit)", "Define evens(numbers)"],
            10,
            driven(
                (
                    """
                    print(count_above([3, 8, 12, 15], 10))
                    print(count_above([], 0))
                    print(count_above([10, 10], 10))
                    print(evens([1, 2, 3, 4, 10]))
                    print(evens([7, 9]))
                    print(parse_numbers("1,2"))
                    """,
                    "2\n0\n0\n[2, 4, 10]\n[]\n[1, 2]\n",
                ),
                requires={
                    "functions": ["parse_numbers", "count_above", "evens"],
                    "constructs": ["for", "if"],
                },
            ),
        ),
        stage(
            "statistics",
            "Calculate statistics",
            "Summarise a list: count, smallest, largest and average.",
            """
            Write stats(numbers). It returns a dictionary with the keys "count", "min", "max"
            and "average". Round the average to 2 decimal places. For an empty list return
            {"count": 0, "min": None, "max": None, "average": None}.
            Try finding the smallest and largest with a loop rather than min() and max().
            """,
            ["Define stats(numbers)", "Handle an empty list", "Round the average to 2 places"],
            12,
            function_spec(
                "stats",
                [
                    ([[3, 8, 12]], {"count": 3, "min": 3, "max": 12, "average": 7.67}),
                    ([[]], {"count": 0, "min": None, "max": None, "average": None}),
                    ([[-5]], {"count": 1, "min": -5, "max": -5, "average": -5}),
                    ([[2, 4, 4, 1]], {"count": 4, "min": 1, "max": 4, "average": 2.75}),
                ],
                requires={"functions": ["stats"], "constructs": ["for"]},
            ),
        ),
        stage(
            "report",
            "Produce the report",
            "Combine everything into a readable report.",
            """
            Write report(text). It uses your other functions and returns one string with these
            lines (joined with newlines):

                Numbers: 3, 8, 12
                Count: 3
                Min: 3
                Max: 12
                Average: 7.67
                Above 10: 1

            The average always has 2 decimal places. If the text has no numbers, return
            "No numbers to analyse." instead.
            """,
            [
                "Define report(text)",
                "Reuse parse_numbers, stats and count_above",
                "Match the format",
            ],
            13,
            function_spec(
                "report",
                [
                    (
                        ["3, 8, 12"],
                        "Numbers: 3, 8, 12\nCount: 3\nMin: 3\nMax: 12\nAverage: 7.67\nAbove 10: 1",
                    ),
                    ([" , "], "No numbers to analyse."),
                    (
                        ["20,30"],
                        "Numbers: 20, 30\nCount: 2\nMin: 20\nMax: 30\nAverage: 25.00\nAbove 10: 2",
                    ),
                ],
                requires={"functions": ["report", "parse_numbers", "stats", "count_above"]},
            ),
        ),
    ],
}


CONTACT_BOOK = {
    "slug": "contact-book",
    "title": "Contact Book",
    "summary": "Store, find, update and list contacts in a dictionary.",
    "brief": dedent(
        """
        You'll build the core of a contact book. Contacts live in a dictionary that maps a
        name to that person's details, for example
        {"Ana": {"phone": "0711", "email": "ana@example.com"}}.

        Each feature is its own small function: adding, listing, searching, updating,
        deleting and printing a tidy listing.
        """
    ).strip(),
    "order": 2,
    "difficulty": "beginner",
    "estimated_minutes": 50,
    "xp_reward": 150,
    "requirements": [
        "functions/defining-and-calling-functions",
        "functions/return-values",
        "collections/dictionaries",
        "collections/list-mutation",
        "loops/for-loops",
        "decisions/if-statements",
    ],
    "stages": [
        stage(
            "add-and-list",
            "Add and list contacts",
            "Add contacts to the book and list their names.",
            f"""
            Write add_contact(book, name, phone, email). If the name is new, store
            {{"phone": phone, "email": email}} under that name and return True. If the name is
            already in the book, change nothing and return False.
            Then write list_names(book), which returns the names sorted alphabetically.

            {NO_INPUT}
            """,
            ["Define add_contact(book, name, phone, email)", "Define list_names(book)"],
            12,
            driven(
                (
                    """
                    book = {}
                    print(add_contact(book, "Mara", "0722", "mara@example.com"))
                    print(add_contact(book, "Ana", "0711", "ana@example.com"))
                    print(add_contact(book, "Mara", "0000", "other@example.com"))
                    print(book["Mara"])
                    print(list_names(book))
                    print(list_names({}))
                    """,
                    "True\nTrue\nFalse\n{'phone': '0722', 'email': 'mara@example.com'}\n"
                    "['Ana', 'Mara']\n[]\n",
                ),
                requires={"functions": ["add_contact", "list_names"], "constructs": ["if"]},
            ),
            starter="""
                def add_contact(book, name, phone, email):
                    ...


                def list_names(book):
                    ...
            """,
        ),
        stage(
            "find",
            "Find contacts",
            "Search names without caring about upper or lower case.",
            """
            Write find_contacts(book, text). It returns a sorted list of every name that
            contains text, ignoring case. For example "an" matches "Ana" and "Dan".
            """,
            ["Define find_contacts(book, text)", "Ignore case", "Return names sorted"],
            10,
            driven(
                (
                    """
                    book = {}
                    for name in ["Ana", "Dan", "Mara", "Anton"]:
                        add_contact(book, name, "07", name.lower() + "@example.com")
                    print(find_contacts(book, "an"))
                    print(find_contacts(book, "MAR"))
                    print(find_contacts(book, "zz"))
                    """,
                    "['Ana', 'Anton', 'Dan']\n['Mara']\n[]\n",
                ),
                requires={"functions": ["find_contacts"], "constructs": ["for"]},
            ),
        ),
        stage(
            "update-and-delete",
            "Update and delete",
            "Change a phone number and remove contacts safely.",
            """
            Write update_phone(book, name, phone) and delete_contact(book, name). Each returns
            True when it changed the book, or False when the name isn't there (and then
            changes nothing).
            """,
            ["Define update_phone(book, name, phone)", "Define delete_contact(book, name)"],
            12,
            driven(
                (
                    """
                    book = {}
                    add_contact(book, "Ana", "0711", "ana@example.com")
                    add_contact(book, "Dan", "0733", "dan@example.com")
                    print(update_phone(book, "Ana", "0799"))
                    print(update_phone(book, "Zoe", "0100"))
                    print(book["Ana"]["phone"])
                    print(delete_contact(book, "Dan"))
                    print(delete_contact(book, "Dan"))
                    print(list_names(book))
                    """,
                    "True\nFalse\n0799\nTrue\nFalse\n['Ana']\n",
                ),
                requires={"functions": ["update_phone", "delete_contact"]},
            ),
        ),
        stage(
            "listing",
            "Formatted listing",
            "Print the whole book in a readable way.",
            """
            Write format_book(book). It returns one string with a line per contact, sorted by
            name, in the form "Ana: 0711, ana@example.com", joined with newlines. For an empty
            book, return "Your contact book is empty."
            """,
            ["Define format_book(book)", "Sort by name", "Handle an empty book"],
            12,
            driven(
                (
                    """
                    book = {}
                    print(format_book(book))
                    add_contact(book, "Mara", "0722", "mara@example.com")
                    add_contact(book, "Ana", "0711", "ana@example.com")
                    print(format_book(book))
                    """,
                    "Your contact book is empty.\n"
                    "Ana: 0711, ana@example.com\nMara: 0722, mara@example.com\n",
                ),
                requires={"functions": ["format_book"], "constructs": ["for"]},
            ),
        ),
    ],
}


EXPENSE_TRACKER = {
    "slug": "expense-tracker",
    "title": "Expense Tracker",
    "summary": "Read spending from a CSV file, total it by category and save a report.",
    "brief": dedent(
        """
        You'll build an expense tracker that works with a real file. The checker gives your
        program a file called transactions.csv with the columns date,category,amount. Some
        lines are broken on purpose, and your tracker must skip them instead of crashing.

        You'll parse lines, load the file safely, total spending per category and write a
        report file.
        """
    ).strip(),
    "order": 3,
    "difficulty": "intermediate",
    "estimated_minutes": 60,
    "xp_reward": 200,
    "requirements": [
        "functions/parameters",
        "collections/dictionaries",
        "real-data/files",
        "real-data/csv",
        "debugging/runtime-errors",
    ],
    "stages": [
        stage(
            "parse-transactions",
            "Parse a transaction",
            "Turn one CSV line into a dictionary, rejecting broken lines.",
            f"""
            Write parse_line(line). A line such as "2026-01-03,food,12.50" becomes
            {{"date": "2026-01-03", "category": "food", "amount": 12.5}} (amount as a float).
            Strip the line first. If it doesn't have exactly 3 fields, raise ValueError.
            A non-numeric amount raises ValueError too (float() already does that).

            {NO_INPUT}
            """,
            [
                "Define parse_line(line)",
                "Return amount as a float",
                "Raise ValueError for bad lines",
            ],
            12,
            driven(
                (
                    """
                    print(parse_line("2026-01-03,food,12.50"))
                    print(parse_line("2026-02-05,fun,15\\n"))
                    for bad in ["bad line", "2026-02-02,food,oops", "a,b,c,d"]:
                        try:
                            parse_line(bad)
                            print("accepted")
                        except ValueError:
                            print("rejected")
                    """,
                    "{'date': '2026-01-03', 'category': 'food', 'amount': 12.5}\n"
                    "{'date': '2026-02-05', 'category': 'fun', 'amount': 15.0}\n"
                    "rejected\nrejected\nrejected\n",
                ),
                requires={"functions": ["parse_line"]},
            ),
            starter="""
                def parse_line(line):
                    ...
            """,
        ),
        stage(
            "load-the-file",
            "Load the file safely",
            "Read transactions.csv and skip the lines that can't be parsed.",
            """
            Write load_transactions(filename). Open the file, skip the header line, and parse
            every other line with parse_line. Use try/except ValueError so a broken line is
            skipped instead of stopping the program. Return the list of transactions.
            """,
            [
                "Define load_transactions(filename)",
                "Open the file",
                "Use try/except to skip bad lines",
            ],
            15,
            driven(
                (
                    """
                    items = load_transactions("transactions.csv")
                    print(len(items))
                    print(items[0]["category"], items[-1]["amount"])
                    """,
                    "6\nfood 4.8\n",
                ),
                requires={
                    "functions": ["load_transactions"],
                    "constructs": ["try", "open"],
                },
                fixtures={"transactions.csv": TRANSACTIONS_CSV},
            ),
        ),
        stage(
            "category-totals",
            "Category totals",
            "Add up the spending for each category.",
            """
            Write category_totals(transactions). It returns a dictionary mapping each category
            to its total amount, rounded to 2 decimal places, with categories in the order they
            first appear.
            """,
            ["Define category_totals(transactions)", "Use a dictionary", "Round to 2 places"],
            13,
            driven(
                (
                    """
                    totals = category_totals(load_transactions("transactions.csv"))
                    print(totals)
                    print(category_totals([]))
                    """,
                    "{'food': 19.75, 'transport': 8.0, 'rent': 500.0, 'fun': 15.0}\n{}\n",
                ),
                requires={"functions": ["category_totals"], "constructs": ["for"]},
                fixtures={"transactions.csv": TRANSACTIONS_CSV},
            ),
        ),
        stage(
            "save-a-report",
            "Save a report",
            "Write the totals to a report file.",
            """
            Write save_report(totals, filename). It writes one line per category, sorted by
            category, in the form "food: 19.75" (always 2 decimal places), and returns how many
            lines it wrote. Use a with block so the file is closed properly.
            """,
            [
                "Define save_report(totals, filename)",
                "Use with open(...)",
                "Return the number of lines",
            ],
            15,
            driven(
                (
                    """
                    totals = category_totals(load_transactions("transactions.csv"))
                    print(save_report(totals, "report.txt"))
                    with open("report.txt") as report_file:
                        print(report_file.read(), end="")
                    """,
                    "4\nfood: 19.75\nfun: 15.00\nrent: 500.00\ntransport: 8.00\n",
                ),
                requires={"functions": ["save_report"], "constructs": ["with"]},
                fixtures={"transactions.csv": TRANSACTIONS_CSV},
            ),
        ),
    ],
}


INVENTORY_MANAGER = {
    "slug": "inventory-manager",
    "title": "Inventory Manager",
    "summary": "Model products and stock with classes, then save and load them as JSON.",
    "brief": dedent(
        """
        You'll build a small inventory application for a shop. Products are objects, the
        inventory is an object that manages them, and stock is saved to and loaded from a
        JSON file.

        The checker gives your program a file called inventory.json. A few of its entries
        are invalid on purpose, and your loader must skip them.
        """
    ).strip(),
    "order": 4,
    "difficulty": "intermediate",
    "estimated_minutes": 70,
    "xp_reward": 200,
    "requirements": [
        "oop-basics/classes-and-objects",
        "oop-basics/init-method",
        "oop-basics/methods",
        "real-data/json",
        "debugging/runtime-errors",
    ],
    "stages": [
        stage(
            "product",
            "The Product class",
            "Represent one product with a name, price and quantity.",
            f"""
            Write a class Product. Its __init__(self, name, price, quantity) stores the three
            values as attributes with the same names. Add a method value(self) that returns
            price * quantity rounded to 2 decimal places.

            {NO_INPUT}
            """,
            ["Define class Product", "Store name, price and quantity", "Add value()"],
            12,
            driven(
                (
                    """
                    pen = Product("pen", 1.5, 10)
                    print(pen.name, pen.price, pen.quantity)
                    print(f"{pen.value():.2f}")
                    print(f"{Product('cable', 3.333, 3).value():.2f}")
                    """,
                    "pen 1.5 10\n15.00\n10.00\n",
                ),
                requires={
                    "classes": ["Product"],
                    "methods": ["Product.__init__", "Product.value"],
                },
            ),
            starter="""
                class Product:
                    def __init__(self, name, price, quantity):
                        ...
            """,
        ),
        stage(
            "inventory",
            "The Inventory class",
            "Add and remove stock, refusing impossible removals.",
            """
            Write a class Inventory that keeps products by name.
            - add(product): store the product, or if one with the same name exists, increase
              its quantity by product.quantity.
            - remove(name, quantity): raise ValueError if the product doesn't exist or there
              isn't enough stock. Otherwise reduce the quantity, and delete the product when
              it reaches 0.
            - quantity_of(name): the product's quantity, or 0 if it isn't stocked.
            """,
            [
                "Define class Inventory",
                "add, remove and quantity_of methods",
                "Raise ValueError when needed",
            ],
            18,
            driven(
                (
                    """
                    shop = Inventory()
                    shop.add(Product("pen", 1.5, 10))
                    shop.add(Product("pen", 1.5, 5))
                    shop.add(Product("bag", 25.0, 1))
                    print(shop.quantity_of("pen"), shop.quantity_of("cup"))
                    shop.remove("pen", 3)
                    print(shop.quantity_of("pen"))
                    for name, amount in [("cup", 1), ("bag", 2)]:
                        try:
                            shop.remove(name, amount)
                            print("removed")
                        except ValueError:
                            print("refused")
                    shop.remove("bag", 1)
                    print(shop.quantity_of("bag"))
                    """,
                    "15 0\n12\nrefused\nrefused\n0\n",
                ),
                requires={
                    "classes": ["Product", "Inventory"],
                    "methods": ["Inventory.add", "Inventory.remove", "Inventory.quantity_of"],
                },
            ),
        ),
        stage(
            "stock-value",
            "Stock value",
            "Report the value of the stock and what is running low.",
            """
            Add two methods to Inventory:
            - total_value(): the sum of every product's value(), rounded to 2 decimal places.
            - low_stock(limit): a sorted list of product names whose quantity is limit or less.
            """,
            ["Add total_value()", "Add low_stock(limit)"],
            15,
            driven(
                (
                    """
                    shop = Inventory()
                    print(f"{shop.total_value():.2f}", shop.low_stock(5))
                    shop.add(Product("pen", 1.5, 10))
                    shop.add(Product("notebook", 3.0, 4))
                    shop.add(Product("bag", 25.0, 1))
                    print(f"{shop.total_value():.2f}")
                    print(shop.low_stock(4))
                    """,
                    "0.00 []\n52.00\n['bag', 'notebook']\n",
                ),
                requires={"methods": ["Inventory.total_value", "Inventory.low_stock"]},
            ),
        ),
        stage(
            "save-and-load",
            "Save and load",
            "Persist the inventory as JSON and load it back safely.",
            """
            Use the json module.
            - Add a method save(filename) that writes a JSON list of
              {"name": ..., "price": ..., "quantity": ...} objects, sorted by name.
            - Write a function load_inventory(filename) that reads such a file and returns an
              Inventory. Skip entries with a missing field, a price that isn't a number, or a
              negative quantity (catch KeyError, TypeError and ValueError).
              Entries with the same name are combined by add().
            """,
            [
                "import json",
                "Add Inventory.save(filename)",
                "Define load_inventory(filename)",
                "Skip invalid entries with try/except",
            ],
            20,
            driven(
                (
                    """
                    shop = load_inventory("inventory.json")
                    for name in ["pen", "broken", "ghost"]:
                        print(shop.quantity_of(name))
                    print(f"{shop.total_value():.2f}")
                    shop.remove("notebook", 4)
                    shop.save("saved.json")
                    again = load_inventory("saved.json")
                    print(again.low_stock(100))
                    print(f"{again.total_value():.2f}")
                    """,
                    "12\n0\n0\n55.00\n['bag', 'pen']\n43.00\n",
                ),
                requires={
                    "functions": ["load_inventory"],
                    "methods": ["Inventory.save"],
                    "constructs": ["import", "try", "open"],
                },
                fixtures={"inventory.json": INVENTORY_JSON},
            ),
        ),
    ],
}


PERSONAL_FINANCE = {
    "slug": "personal-finance-manager",
    "title": "Personal Finance Manager",
    "summary": "The capstone: accounts, budgets, a bank statement import and a monthly report.",
    "brief": dedent(
        """
        Your final Python Foundations project is a personal finance manager, a complete
        command-line application. It has an Account class that refuses invalid operations,
        budget categories, an importer for a bank statement file (statement.csv, with a
        broken row to skip) and a monthly summary. It finishes as a program that prints a
        finance report when you run it.

        It brings together almost everything from the course: variables, conditions, loops,
        lists, dictionaries, functions, files, error handling, classes and the main guard.
        """
    ).strip(),
    "order": 5,
    "difficulty": "advanced",
    "estimated_minutes": 100,
    "xp_reward": 250,
    "requirements": [
        "loops/while-loops",
        "functions/return-values",
        "collections/dictionaries",
        "real-data/csv",
        "real-data/data-transformation",
        "debugging/runtime-errors",
        "oop-basics/methods",
        "python-structure/main-guard",
    ],
    "stages": [
        stage(
            "account",
            "The Account class",
            "An account that keeps a balance and a history, and refuses bad operations.",
            f"""
            Write a class Account. __init__(self, name) stores the name, sets balance to 0 and
            history to an empty list.
            - deposit(amount) adds to the balance and appends ("deposit", amount) to history.
            - withdraw(amount) subtracts and appends ("withdraw", amount).
            Both raise ValueError if amount is 0 or negative. withdraw also raises ValueError
            if the amount is more than the balance.

            {NO_INPUT}
            """,
            [
                "Define class Account",
                "deposit and withdraw methods",
                "Raise ValueError for invalid amounts",
            ],
            18,
            driven(
                (
                    """
                    account = Account("Ana")
                    account.deposit(100)
                    account.withdraw(30.5)
                    print(account.name, f"{account.balance:.2f}")
                    print(account.history)
                    for action, amount in [("withdraw", 500), ("deposit", -5), ("withdraw", 0)]:
                        try:
                            getattr(account, action)(amount)
                            print("accepted")
                        except ValueError:
                            print("refused")
                    print(f"{account.balance:.2f}", len(account.history))
                    """,
                    "Ana 69.50\n[('deposit', 100), ('withdraw', 30.5)]\n"
                    "refused\nrefused\nrefused\n69.50 2\n",
                ),
                requires={
                    "classes": ["Account"],
                    "methods": ["Account.__init__", "Account.deposit", "Account.withdraw"],
                },
            ),
            starter="""
                class Account:
                    def __init__(self, name):
                        ...
            """,
        ),
        stage(
            "budget-categories",
            "Budget categories",
            "Sort spending into categories and see what's left of each budget.",
            """
            Write two functions:
            - categorise(description, rules): rules maps keywords to categories, for example
              {"grocer": "food", "rent": "home"}. Return the category of the first keyword
              found in the description (ignoring case), or "other".
            - budget_left(budgets, spent): for every category in budgets, return the budget
              minus what was spent (0 if nothing was spent), rounded to 2 decimal places.
            """,
            ["Define categorise(description, rules)", "Define budget_left(budgets, spent)"],
            15,
            driven(
                (
                    """
                    rules = {"grocer": "food", "rent": "home", "cinema": "fun"}
                    for text in ["Groceries", "RENT March", "Cinema night", "Salary"]:
                        print(categorise(text, rules))
                    print(budget_left({"food": 300.0, "fun": 50.0}, {"food": 94.5}))
                    """,
                    "food\nhome\nfun\nother\n{'food': 205.5, 'fun': 50.0}\n",
                ),
                requires={"functions": ["categorise", "budget_left"], "constructs": ["for"]},
            ),
        ),
        stage(
            "import-statement",
            "Import the bank statement",
            "Read statement.csv line by line with a while loop, skipping bad rows.",
            """
            Write load_statement(filename). Open the file and skip the header. Then read it one
            line at a time with readline() in a while loop (readline() returns "" at the end).
            Each row "2026-03-02,Groceries,-54.20" becomes
            {"date": "2026-03-02", "month": "2026-03", "description": "Groceries",
             "amount": -54.2}. Skip any row that doesn't have 3 fields or whose amount isn't a
            number, using try/except ValueError. Return the list of rows.
            """,
            [
                "Define load_statement(filename)",
                "Use a while loop with readline()",
                "Skip bad rows with try/except",
            ],
            20,
            driven(
                (
                    """
                    rows = load_statement("statement.csv")
                    print(len(rows))
                    print(rows[1])
                    print(sorted({row["month"] for row in rows}))
                    """,
                    "8\n{'date': '2026-03-02', 'month': '2026-03', 'description': 'Groceries', "
                    "'amount': -54.2}\n['2026-03', '2026-04']\n",
                ),
                requires={
                    "functions": ["load_statement"],
                    "constructs": ["while", "try", "open"],
                },
                fixtures={"statement.csv": STATEMENT_CSV},
            ),
        ),
        stage(
            "monthly-summary",
            "Monthly summary",
            "Group the statement by month into income, spending and net.",
            """
            Write monthly_summary(transactions). It returns a dictionary with one entry per
            month, in the order months first appear, like
            {"2026-03": {"income": 2000.0, "spending": 907.0, "net": 1093.0}}.
            Positive amounts are income, negative amounts count as spending (as a positive
            number), and net is income minus spending. Round everything to 2 decimal places.
            """,
            ["Define monthly_summary(transactions)", "Keep months in order", "Round to 2 places"],
            20,
            driven(
                (
                    """
                    summary = monthly_summary(load_statement("statement.csv"))
                    for month, totals in summary.items():
                        values = [totals["income"], totals["spending"], totals["net"]]
                        print(month, *[f"{value:.2f}" for value in values])
                    print(monthly_summary([]))
                    """,
                    "2026-03 2000.00 907.00 1093.00\n2026-04 2000.00 861.00 1139.00\n{}\n",
                ),
                requires={"functions": ["monthly_summary"]},
                fixtures={"statement.csv": STATEMENT_CSV},
            ),
        ),
        stage(
            "finance-report",
            "The finance report app",
            "Finish the application: running the file prints the monthly report.",
            """
            Write main(). It loads statement.csv, builds the monthly summary and prints:

                Personal Finance Report
                2026-03: income 2000.00, spending 907.00, net 1093.00
                2026-04: income 2000.00, spending 861.00, net 1139.00
                Overall net: 2232.00

            Call main() only inside an if __name__ == "__main__": block at the bottom of the
            file. The checker runs your file as a program and also checks that your Account
            class still works.
            """,
            ["Define main()", "Use the main guard", "Print the report exactly"],
            27,
            {
                "strategy": "stdout",
                "tests": [
                    {
                        "stdin": "",
                        "expected_stdout": (
                            "Personal Finance Report\n"
                            "2026-03: income 2000.00, spending 907.00, net 1093.00\n"
                            "2026-04: income 2000.00, spending 861.00, net 1139.00\n"
                            "Overall net: 2232.00\n"
                        ),
                    },
                    {
                        "stdin": "",
                        "driver": code(
                            """
                            account = Account("Test")
                            account.deposit(100)
                            try:
                                account.withdraw(500)
                            except ValueError:
                                print("refused")
                            print(f"{account.balance:.2f}")
                            """
                        ),
                        "expected_stdout": "refused\n100.00\n",
                    },
                ],
                "requires": {
                    "functions": ["main", "load_statement", "monthly_summary"],
                    "classes": ["Account"],
                    "constructs": ["main_guard"],
                },
                "fixtures": {"statement.csv": STATEMENT_CSV},
            },
        ),
    ],
}


PROJECTS = [NUMBER_ANALYZER, CONTACT_BOOK, EXPENSE_TRACKER, INVENTORY_MANAGER, PERSONAL_FINANCE]
