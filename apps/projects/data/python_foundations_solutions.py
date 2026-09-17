"""Reference solutions for the Python Foundations projects.

Used ONLY by the opt-in Docker integration test to prove every seeded stage is solvable.
They are never stored in the database, shown to learners or sent to the AI tutor.
Each entry is the complete program as it could look after that stage (code carries forward).
"""

NUMBER_ANALYZER_1 = """
def parse_numbers(text):
    numbers = []
    for part in text.split(","):
        part = part.strip()
        if part:
            numbers.append(int(part))
    return numbers
"""

NUMBER_ANALYZER_2 = (
    NUMBER_ANALYZER_1
    + """

def count_above(numbers, limit):
    count = 0
    for number in numbers:
        if number > limit:
            count += 1
    return count


def evens(numbers):
    result = []
    for number in numbers:
        if number % 2 == 0:
            result.append(number)
    return result
"""
)

NUMBER_ANALYZER_3 = (
    NUMBER_ANALYZER_2
    + """

def stats(numbers):
    if not numbers:
        return {"count": 0, "min": None, "max": None, "average": None}
    smallest = numbers[0]
    largest = numbers[0]
    total = 0
    for number in numbers:
        if number < smallest:
            smallest = number
        if number > largest:
            largest = number
        total += number
    return {
        "count": len(numbers),
        "min": smallest,
        "max": largest,
        "average": round(total / len(numbers), 2),
    }
"""
)

NUMBER_ANALYZER_4 = (
    NUMBER_ANALYZER_3
    + """

def report(text):
    numbers = parse_numbers(text)
    if not numbers:
        return "No numbers to analyse."
    summary = stats(numbers)
    lines = [
        "Numbers: " + ", ".join(str(number) for number in numbers),
        f"Count: {summary['count']}",
        f"Min: {summary['min']}",
        f"Max: {summary['max']}",
        f"Average: {summary['average']:.2f}",
        f"Above 10: {count_above(numbers, 10)}",
    ]
    return "\\n".join(lines)
"""
)

CONTACT_BOOK_1 = """
def add_contact(book, name, phone, email):
    if name in book:
        return False
    book[name] = {"phone": phone, "email": email}
    return True


def list_names(book):
    return sorted(book)
"""

CONTACT_BOOK_2 = (
    CONTACT_BOOK_1
    + """

def find_contacts(book, text):
    matches = []
    for name in book:
        if text.lower() in name.lower():
            matches.append(name)
    return sorted(matches)
"""
)

CONTACT_BOOK_3 = (
    CONTACT_BOOK_2
    + """

def update_phone(book, name, phone):
    if name not in book:
        return False
    book[name]["phone"] = phone
    return True


def delete_contact(book, name):
    if name not in book:
        return False
    del book[name]
    return True
"""
)

CONTACT_BOOK_4 = (
    CONTACT_BOOK_3
    + """

def format_book(book):
    if not book:
        return "Your contact book is empty."
    lines = []
    for name in list_names(book):
        contact = book[name]
        lines.append(f"{name}: {contact['phone']}, {contact['email']}")
    return "\\n".join(lines)
"""
)

EXPENSE_TRACKER_1 = """
def parse_line(line):
    parts = line.strip().split(",")
    if len(parts) != 3:
        raise ValueError("expected date,category,amount")
    date, category, amount = parts
    return {"date": date, "category": category, "amount": float(amount)}
"""

EXPENSE_TRACKER_2 = (
    EXPENSE_TRACKER_1
    + """

def load_transactions(filename):
    transactions = []
    with open(filename) as file:
        next(file)
        for line in file:
            try:
                transactions.append(parse_line(line))
            except ValueError:
                continue
    return transactions
"""
)

EXPENSE_TRACKER_3 = (
    EXPENSE_TRACKER_2
    + """

def category_totals(transactions):
    totals = {}
    for item in transactions:
        category = item["category"]
        totals[category] = round(totals.get(category, 0) + item["amount"], 2)
    return totals
"""
)

EXPENSE_TRACKER_4 = (
    EXPENSE_TRACKER_3
    + """

def save_report(totals, filename):
    lines = [f"{category}: {totals[category]:.2f}" for category in sorted(totals)]
    with open(filename, "w") as file:
        for line in lines:
            file.write(line + "\\n")
    return len(lines)
"""
)

INVENTORY_1 = """
class Product:
    def __init__(self, name, price, quantity):
        self.name = name
        self.price = price
        self.quantity = quantity

    def value(self):
        return round(self.price * self.quantity, 2)
"""

INVENTORY_2 = (
    INVENTORY_1
    + """

class Inventory:
    def __init__(self):
        self.products = {}

    def add(self, product):
        if product.name in self.products:
            self.products[product.name].quantity += product.quantity
        else:
            self.products[product.name] = product

    def remove(self, name, quantity):
        if name not in self.products:
            raise ValueError("unknown product")
        product = self.products[name]
        if quantity > product.quantity:
            raise ValueError("not enough stock")
        product.quantity -= quantity
        if product.quantity == 0:
            del self.products[name]

    def quantity_of(self, name):
        if name in self.products:
            return self.products[name].quantity
        return 0
"""
)

INVENTORY_3 = INVENTORY_2.replace(
    """    def quantity_of(self, name):""",
    """    def total_value(self):
        total = 0
        for product in self.products.values():
            total += product.value()
        return round(total, 2)

    def low_stock(self, limit):
        return sorted(
            name for name, product in self.products.items() if product.quantity <= limit
        )

    def quantity_of(self, name):""",
)

INVENTORY_4 = (
    "import json\n"
    + INVENTORY_3.replace(
        """    def quantity_of(self, name):""",
        """    def save(self, filename):
        rows = [
            {"name": p.name, "price": p.price, "quantity": p.quantity}
            for p in sorted(self.products.values(), key=lambda p: p.name)
        ]
        with open(filename, "w") as file:
            json.dump(rows, file)

    def quantity_of(self, name):""",
    )
    + """

def load_inventory(filename):
    inventory = Inventory()
    with open(filename) as file:
        rows = json.load(file)
    for row in rows:
        try:
            price = float(row["price"])
            quantity = int(row["quantity"])
            if quantity < 0:
                raise ValueError("negative quantity")
            inventory.add(Product(row["name"], price, quantity))
        except (KeyError, TypeError, ValueError):
            continue
    return inventory
"""
)

FINANCE_1 = """
class Account:
    def __init__(self, name):
        self.name = name
        self.balance = 0
        self.history = []

    def deposit(self, amount):
        if amount <= 0:
            raise ValueError("amount must be positive")
        self.balance += amount
        self.history.append(("deposit", amount))

    def withdraw(self, amount):
        if amount <= 0:
            raise ValueError("amount must be positive")
        if amount > self.balance:
            raise ValueError("insufficient funds")
        self.balance -= amount
        self.history.append(("withdraw", amount))
"""

FINANCE_2 = (
    FINANCE_1
    + """

def categorise(description, rules):
    text = description.lower()
    for keyword, category in rules.items():
        if keyword.lower() in text:
            return category
    return "other"


def budget_left(budgets, spent):
    left = {}
    for category, budget in budgets.items():
        left[category] = round(budget - spent.get(category, 0), 2)
    return left
"""
)

FINANCE_3 = (
    FINANCE_2
    + """

def load_statement(filename):
    rows = []
    with open(filename) as file:
        file.readline()
        line = file.readline()
        while line:
            parts = line.strip().split(",")
            try:
                if len(parts) != 3:
                    raise ValueError("bad row")
                date, description, amount = parts
                rows.append(
                    {
                        "date": date,
                        "month": date[:7],
                        "description": description,
                        "amount": float(amount),
                    }
                )
            except ValueError:
                pass
            line = file.readline()
    return rows
"""
)

FINANCE_4 = (
    FINANCE_3
    + """

def monthly_summary(transactions):
    summary = {}
    for item in transactions:
        month = summary.setdefault(item["month"], {"income": 0, "spending": 0, "net": 0})
        if item["amount"] >= 0:
            month["income"] = round(month["income"] + item["amount"], 2)
        else:
            month["spending"] = round(month["spending"] - item["amount"], 2)
        month["net"] = round(month["income"] - month["spending"], 2)
    return summary
"""
)

FINANCE_5 = (
    FINANCE_4
    + """

def main():
    summary = monthly_summary(load_statement("statement.csv"))
    print("Personal Finance Report")
    overall = 0
    for month, totals in summary.items():
        print(
            f"{month}: income {totals['income']:.2f}, "
            f"spending {totals['spending']:.2f}, net {totals['net']:.2f}"
        )
        overall += totals["net"]
    print(f"Overall net: {overall:.2f}")


if __name__ == "__main__":
    main()
"""
)

SOLUTIONS = {
    ("number-analyzer", "store-numbers"): NUMBER_ANALYZER_1,
    ("number-analyzer", "count-and-filter"): NUMBER_ANALYZER_2,
    ("number-analyzer", "statistics"): NUMBER_ANALYZER_3,
    ("number-analyzer", "report"): NUMBER_ANALYZER_4,
    ("contact-book", "add-and-list"): CONTACT_BOOK_1,
    ("contact-book", "find"): CONTACT_BOOK_2,
    ("contact-book", "update-and-delete"): CONTACT_BOOK_3,
    ("contact-book", "listing"): CONTACT_BOOK_4,
    ("expense-tracker", "parse-transactions"): EXPENSE_TRACKER_1,
    ("expense-tracker", "load-the-file"): EXPENSE_TRACKER_2,
    ("expense-tracker", "category-totals"): EXPENSE_TRACKER_3,
    ("expense-tracker", "save-a-report"): EXPENSE_TRACKER_4,
    ("inventory-manager", "product"): INVENTORY_1,
    ("inventory-manager", "inventory"): INVENTORY_2,
    ("inventory-manager", "stock-value"): INVENTORY_3,
    ("inventory-manager", "save-and-load"): INVENTORY_4,
    ("personal-finance-manager", "account"): FINANCE_1,
    ("personal-finance-manager", "budget-categories"): FINANCE_2,
    ("personal-finance-manager", "import-statement"): FINANCE_3,
    ("personal-finance-manager", "monthly-summary"): FINANCE_4,
    ("personal-finance-manager", "finance-report"): FINANCE_5,
}
