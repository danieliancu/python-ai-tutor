from apps.exercises.data.python_foundations.builders import (
    CREATE,
    FIX,
    code_stdout,
    fill_gap,
    mcq,
)

SKILL = "oop-basics"

LESSONS = {
    ("classes-and-objects", "blueprints-and-things"): [
        mcq(
            "two-separate-objects",
            "Same object?",
            "What does this program print?",
            snippet="""
                class Dog:
                    pass

                a = Dog()
                b = Dog()
                print(a is b)
            """,
            options=["True", "False", "An error", "Dog"],
            correct="b",
            explanation="Each call to Dog() creates a new, separate object.",
            seconds=35,
            misconceptions=("class-vs-instance",),
        ),
        fill_gap(
            "create-a-book",
            "Make an object",
            "Complete the last line so my_book is a new Book object.",
            template="""
                class Book:
                    pass

                my_book = __
            """,
            answers=["Book()"],
            seconds=30,
            misconceptions=("class-vs-instance",),
        ),
        code_stdout(
            "class-not-instance",
            "Class or object?",
            "The program should print hello, but it crashes with TypeError. Fix it.",
            mode=FIX,
            seconds=80,
            starter="""
                class Greeter:
                    def hello(self):
                        return "hello"

                g = Greeter
                print(g.hello())
            """,
            solution="""
                class Greeter:
                    def hello(self):
                        return "hello"

                g = Greeter()
                print(g.hello())
            """,
            expected="hello\n",
            misconceptions=("class-vs-instance",),
        ),
        code_stdout(
            "two-lamps",
            "Two lamps",
            "Define a class Lamp with no body, create two lamps, give each a room attribute "
            "(kitchen and hall), then print both rooms on separate lines.",
            mode=CREATE,
            seconds=120,
            starter="# Define Lamp, create two objects and set their room",
            solution="""
                class Lamp:
                    pass

                first = Lamp()
                second = Lamp()
                first.room = "kitchen"
                second.room = "hall"
                print(first.room)
                print(second.room)
            """,
            expected="kitchen\nhall\n",
            misconceptions=("class-vs-instance",),
        ),
    ],
    ("attributes", "data-on-objects"): [
        mcq(
            "each-object-own-score",
            "Separate scores",
            "What does this program print?",
            snippet="""
                class Player:
                    pass

                p1 = Player()
                p2 = Player()
                p1.score = 10
                p2.score = 3
                p1.score = p1.score + 5
                print(p1.score, p2.score)
            """,
            options=["15 3", "15 15", "10 3", "18 3"],
            correct="a",
            explanation="Each object keeps its own attributes; changing p1 doesn't touch p2.",
            seconds=40,
            misconceptions=("instance-attributes",),
        ),
        code_stdout(
            "attribute-typo",
            "The balance that won't change",
            "The program should print 50, but prints 0. Fix it.",
            mode=FIX,
            seconds=80,
            starter="""
                class Account:
                    def __init__(self, owner):
                        self.owner = owner
                        self.balance = 0

                acc = Account("Ana")
                acc.balence = 50
                print(acc.balance)
            """,
            solution="""
                class Account:
                    def __init__(self, owner):
                        self.owner = owner
                        self.balance = 0

                acc = Account("Ana")
                acc.balance = 50
                print(acc.balance)
            """,
            expected="50\n",
            misconceptions=("attribute-typo",),
        ),
    ],
    ("methods", "behaviour-on-objects"): [
        mcq(
            "toggle-three-times",
            "Toggle, toggle, toggle",
            "What does this program print?",
            snippet="""
                class Light:
                    def __init__(self):
                        self.on = False

                    def toggle(self):
                        self.on = not self.on

                lamp = Light()
                lamp.toggle()
                lamp.toggle()
                lamp.toggle()
                print(lamp.on)
            """,
            options=["True", "False", "None", "An error"],
            correct="a",
            explanation="Each call flips the value: False → True → False → True.",
            seconds=45,
            misconceptions=("method-state",),
        ),
        fill_gap(
            "self-in-method",
            "Refer to the object",
            "Complete add() so the item is stored on this cart's own list.",
            template="""
                class Cart:
                    def __init__(self):
                        self.items = []

                    def add(self, item):
                        __.items.append(item)
            """,
            answers=["self"],
            seconds=30,
            misconceptions=("self",),
        ),
        code_stdout(
            "method-missing-self",
            "A method without self",
            "The program should print 2, but calling tick() crashes. Fix it.",
            mode=FIX,
            seconds=80,
            starter="""
                class Timer:
                    def __init__(self):
                        self.seconds = 0

                    def tick():
                        self.seconds = self.seconds + 1

                t = Timer()
                t.tick()
                t.tick()
                print(t.seconds)
            """,
            solution="""
                class Timer:
                    def __init__(self):
                        self.seconds = 0

                    def tick(self):
                        self.seconds = self.seconds + 1

                t = Timer()
                t.tick()
                t.tick()
                print(t.seconds)
            """,
            expected="2\n",
            misconceptions=("self",),
        ),
        code_stdout(
            "bank-account",
            "A bank account",
            "Write a BankAccount class with a balance attribute starting at 0, deposit(amount) "
            "and withdraw(amount). withdraw must refuse to go below zero by printing "
            "Insufficient funds. The script at the bottom must then run as written.",
            mode=CREATE,
            seconds=240,
            starter="""
                # Write the BankAccount class here


                account = BankAccount()
                account.deposit(50)
                account.withdraw(20)
                account.withdraw(100)
                print(account.balance)
            """,
            solution="""
                class BankAccount:
                    def __init__(self):
                        self.balance = 0

                    def deposit(self, amount):
                        self.balance = self.balance + amount

                    def withdraw(self, amount):
                        if amount > self.balance:
                            print("Insufficient funds")
                        else:
                            self.balance = self.balance - amount


                account = BankAccount()
                account.deposit(50)
                account.withdraw(20)
                account.withdraw(100)
                print(account.balance)
            """,
            expected="Insufficient funds\n30\n",
            misconceptions=("self", "method-state"),
        ),
    ],
    ("init-method", "setting-up-new-objects"): [
        mcq(
            "when-init-runs",
            "When does __init__ run?",
            "When does a class's __init__ method run?",
            options=[
                "Automatically, every time a new object is created",
                "Only when you call obj.__init__() yourself",
                "Once, when the class is defined",
                "Whenever any method of the object is called",
            ],
            correct="a",
            explanation="Creating an object, e.g. Pet('Rex'), calls __init__ on the new object.",
            seconds=30,
            misconceptions=("init",),
        ),
        code_stdout(
            "init-forgets-self",
            "A name that isn't stored",
            "The program should print Rex, but crashes with AttributeError. Fix __init__.",
            mode=FIX,
            seconds=75,
            starter="""
                class Pet:
                    def __init__(self, name):
                        name = name

                rex = Pet("Rex")
                print(rex.name)
            """,
            solution="""
                class Pet:
                    def __init__(self, name):
                        self.name = name

                rex = Pet("Rex")
                print(rex.name)
            """,
            expected="Rex\n",
            misconceptions=("init", "self"),
        ),
    ],
    ("basic-inheritance", "specialising-a-class"): [
        mcq(
            "override-or-inherit",
            "Which speak()?",
            "What does this program print?",
            snippet="""
                class Animal:
                    def speak(self):
                        return "..."

                class Cat(Animal):
                    def speak(self):
                        return "Meow"

                class Fish(Animal):
                    pass

                print(Cat().speak(), Fish().speak())
            """,
            options=["Meow ...", "Meow Meow", "... ...", "An error"],
            correct="a",
            explanation="Cat overrides speak(); Fish inherits Animal's version.",
            seconds=45,
            misconceptions=("inheritance-lookup",),
        ),
        code_stdout(
            "bike-subclass",
            "A bike is a vehicle",
            "Write a Bike class that inherits from Vehicle. Its __init__ takes only a name and "
            "uses super().__init__ to set wheels to 2.",
            mode=CREATE,
            seconds=180,
            starter="""
                class Vehicle:
                    def __init__(self, name, wheels):
                        self.name = name
                        self.wheels = wheels

                    def describe(self):
                        return f"{self.name} has {self.wheels} wheels"

                # Write the Bike class here


                print(Vehicle("Van", 4).describe())
                print(Bike("Racer").describe())
            """,
            solution="""
                class Vehicle:
                    def __init__(self, name, wheels):
                        self.name = name
                        self.wheels = wheels

                    def describe(self):
                        return f"{self.name} has {self.wheels} wheels"


                class Bike(Vehicle):
                    def __init__(self, name):
                        super().__init__(name, 2)


                print(Vehicle("Van", 4).describe())
                print(Bike("Racer").describe())
            """,
            expected="Van has 4 wheels\nRacer has 2 wheels\n",
            misconceptions=("inheritance-lookup", "init"),
        ),
    ],
}
