"""Python Foundations curriculum definition, applied by ``manage.py seed_curriculum``.

Identity is slug-based: World by slug, Skill by (world, slug), Concept by (skill, slug) and
Lesson by (concept, slug). Concept prerequisites use "skill-slug/concept-slug" references.
Order values come from each item's position in its list.
"""

LEARN = "learn"
PRACTICE = "practice"
REVIEW = "review"
CHALLENGE = "challenge"


def lesson(
    slug: str, title: str, objective: str, minutes: int, kind: str = LEARN, summary: str = ""
) -> dict:
    return {
        "slug": slug,
        "title": title,
        "objective": objective,
        "estimated_minutes": minutes,
        "kind": kind,
        "summary": summary,
    }


def concept(
    slug: str, title: str, description: str, learning_objective: str, lessons: list[dict]
) -> dict:
    return {
        "slug": slug,
        "title": title,
        "description": description,
        "learning_objective": learning_objective,
        "lessons": lessons,
    }


WORLD = {
    "slug": "python-foundations",
    "title": "Python Foundations",
    "domain": "python",
    "description": (
        "Learn to write, read and debug real Python programs, from your first print() to a "
        "small end-to-end project."
    ),
    "order": 1,
}

SKILLS = [
    {
        "slug": "start",
        "title": "Start",
        "description": "Run your first Python code and see how Python evaluates what you write.",
        "concepts": [
            concept(
                "running-python",
                "Running Python",
                "How Python code is executed as a script and in the interactive interpreter.",
                "Run Python code as a script and in the interactive interpreter, and explain "
                "that statements execute from top to bottom.",
                [
                    lesson(
                        "your-first-program",
                        "Your first program",
                        "Write and run a one-line Python program and observe its result.",
                        6,
                    )
                ],
            ),
            concept(
                "print-and-output",
                "Print and Output",
                "Producing output with print(), including multiple values and separators.",
                "Use print() to display text and values, including several values in one call "
                "and custom sep and end arguments.",
                [
                    lesson(
                        "printing-values",
                        "Printing values",
                        "Display text and numbers with print() and control how they are separated.",
                        7,
                    )
                ],
            ),
            concept(
                "comments",
                "Comments",
                "Writing notes for humans that Python ignores.",
                "Write single-line comments that explain intent, and predict that Python "
                "ignores everything after # on a line.",
                [
                    lesson(
                        "explaining-code-with-comments",
                        "Explaining code with comments",
                        "Add comments that explain why code exists without changing what it does.",
                        5,
                    )
                ],
            ),
            concept(
                "expressions",
                "Expressions",
                "Arithmetic expressions, operator precedence and evaluation.",
                "Evaluate arithmetic expressions using +, -, *, /, //, % and **, and predict "
                "results that depend on operator precedence and parentheses.",
                [
                    lesson(
                        "python-as-a-calculator",
                        "Python as a calculator",
                        "Predict and verify the value of arithmetic expressions.",
                        8,
                    )
                ],
            ),
        ],
    },
    {
        "slug": "variables",
        "title": "Variables",
        "description": "Store, name and convert the values your programs work with.",
        "concepts": [
            concept(
                "variables-and-values",
                "Variables and Values",
                "Binding names to values and reassigning them.",
                "Assign values to variables, reassign them, and trace the current value of a "
                "variable through a sequence of statements.",
                [
                    lesson(
                        "storing-values",
                        "Storing values in variables",
                        "Create variables, update them and trace their values line by line.",
                        8,
                    )
                ],
            ),
            concept(
                "basic-types",
                "Basic Types",
                "Strings, integers, floats and booleans.",
                "Distinguish str, int, float and bool values, identify a value's type with "
                "type(), and predict how operators behave for each type.",
                [
                    lesson(
                        "strings-numbers-booleans",
                        "Strings, numbers and booleans",
                        "Recognise the four basic types and what each operator does with them.",
                        10,
                    )
                ],
            ),
            concept(
                "naming",
                "Naming",
                "Valid, readable variable names and Python naming conventions.",
                "Choose valid, descriptive snake_case variable names and recognise names that "
                "are invalid or shadow built-ins.",
                [
                    lesson(
                        "good-variable-names",
                        "Choosing good names",
                        "Tell valid names from invalid ones and pick names that explain intent.",
                        5,
                    )
                ],
            ),
            concept(
                "user-input",
                "User Input",
                "Reading text from the user with input().",
                "Use input() to read text from the user, show a helpful prompt, and remember "
                "that input() always returns a string.",
                [
                    lesson(
                        "asking-the-user",
                        "Asking the user for input",
                        "Read a value with input() and use it in the program's output.",
                        7,
                    )
                ],
            ),
            concept(
                "type-conversion",
                "Type Conversion",
                "Converting between str, int, float and bool.",
                "Convert values between basic types with int(), float(), str() and bool(), and "
                "predict when a conversion raises ValueError.",
                [
                    lesson(
                        "converting-types",
                        "Converting between types",
                        "Turn user input into numbers and format numbers back into text.",
                        9,
                    )
                ],
            ),
        ],
    },
    {
        "slug": "decisions",
        "title": "Decisions",
        "description": "Make programs choose what to do based on conditions.",
        "concepts": [
            concept(
                "booleans",
                "Booleans",
                "True, False and values that behave as true or false.",
                "Use True and False as values, and predict the truthiness of numbers, strings "
                "and empty collections.",
                [
                    lesson(
                        "true-and-false",
                        "True and False",
                        "Work with boolean values and predict truthiness.",
                        6,
                    )
                ],
            ),
            concept(
                "comparison-operators",
                "Comparison Operators",
                "Comparing values with <, >, <=, >=, == and !=.",
                "Use the comparison operators <, >, <=, >=, == and != to build boolean "
                "conditions, choose the correct direction of a comparison, and distinguish "
                "inclusive (<=, >=) from exclusive (<, >) comparisons.",
                [
                    lesson(
                        "comparing-values",
                        "Comparing values",
                        "Build conditions with each comparison operator and predict their result.",
                        9,
                    ),
                    lesson(
                        "inclusive-or-exclusive",
                        "Inclusive or exclusive?",
                        "Choose between > and >= (and < and <=) to match a written requirement "
                        "exactly, including the boundary value.",
                        8,
                        kind=PRACTICE,
                    ),
                ],
            ),
            concept(
                "if-statements",
                "If Statements",
                "Running code only when a condition is true.",
                "Write if statements with correctly indented blocks that run only when their "
                "condition is true.",
                [
                    lesson(
                        "making-a-decision",
                        "Making a decision with if",
                        "Guard a block of code with an if statement.",
                        8,
                    )
                ],
            ),
            concept(
                "elif-and-else",
                "Elif and Else",
                "Choosing one branch among several.",
                "Use elif and else to select exactly one branch from several conditions, and "
                "order the conditions so the intended branch runs.",
                [
                    lesson(
                        "choosing-between-branches",
                        "Choosing between branches",
                        "Extend an if statement with elif and else and trace which branch runs.",
                        9,
                    )
                ],
            ),
            concept(
                "logical-operators",
                "Logical Operators",
                "Combining conditions with and, or and not.",
                "Combine conditions with and, or and not, and predict the result of compound "
                "conditions, including short-circuit evaluation.",
                [
                    lesson(
                        "combining-conditions",
                        "Combining conditions",
                        "Express multi-part rules with and, or and not.",
                        9,
                    )
                ],
            ),
        ],
    },
    {
        "slug": "collections",
        "title": "Collections",
        "description": "Group values into lists, tuples, dictionaries and sets.",
        "concepts": [
            concept(
                "list-basics",
                "List Basics",
                "Creating lists and reading their size and contents.",
                "Create lists of values, find their length with len(), and check membership "
                "with in.",
                [
                    lesson(
                        "your-first-list",
                        "Your first list",
                        "Store several values in a list and ask questions about it.",
                        8,
                    )
                ],
            ),
            concept(
                "indexing-and-slicing",
                "Indexing and Slicing",
                "Reading items and sub-lists by position.",
                "Access list items with zero-based and negative indexes, extract sub-lists "
                "with slices, and recognise when an index is out of range.",
                [
                    lesson(
                        "positions-in-a-list",
                        "Positions in a list",
                        "Read single items and slices, starting from index 0.",
                        10,
                    )
                ],
            ),
            concept(
                "list-mutation",
                "List Mutation",
                "Changing lists in place.",
                "Modify lists in place with item assignment, append(), insert(), remove() and "
                "pop(), and predict the list's contents afterwards.",
                [
                    lesson(
                        "changing-a-list",
                        "Changing a list",
                        "Add, replace and remove items and trace the resulting list.",
                        9,
                    )
                ],
            ),
            concept(
                "tuples",
                "Tuples",
                "Fixed-size, immutable sequences and unpacking.",
                "Create tuples, unpack them into variables, and explain when an immutable "
                "tuple is a better fit than a list.",
                [
                    lesson(
                        "fixed-groups-of-values",
                        "Fixed groups of values",
                        "Use tuples for values that belong together and unpack them.",
                        7,
                    )
                ],
            ),
            concept(
                "dictionaries",
                "Dictionaries",
                "Looking up values by key.",
                "Store and retrieve values by key in a dictionary, add and update entries, and "
                "use get() to handle missing keys safely.",
                [
                    lesson(
                        "looking-things-up",
                        "Looking things up by key",
                        "Model named data with a dictionary and read it safely.",
                        10,
                    )
                ],
            ),
            concept(
                "sets",
                "Sets",
                "Unordered collections of unique values.",
                "Use sets to remove duplicates and test membership, and combine sets with "
                "union and intersection.",
                [
                    lesson(
                        "unique-values",
                        "Working with unique values",
                        "Deduplicate data and compare groups with set operations.",
                        7,
                    )
                ],
            ),
        ],
    },
    {
        "slug": "loops",
        "title": "Loops",
        "description": "Repeat actions and process every item in your data.",
        "concepts": [
            concept(
                "for-loops",
                "For Loops",
                "Repeating an action for each item in an iterable.",
                "Use a for loop to iterate through a collection and perform an action for "
                "each element, including accumulating a result.",
                [
                    lesson(
                        "looping-over-a-list",
                        "Looping over a list",
                        "Visit every item in a list and act on it.",
                        9,
                    ),
                    lesson(
                        "filtering-while-looping",
                        "Filtering while looping",
                        "Combine a for loop with an if statement to act only on matching items.",
                        8,
                        kind=REVIEW,
                    ),
                ],
            ),
            concept(
                "range",
                "range()",
                "Generating integer sequences with range().",
                "Use range(start, stop, step) to generate integer sequences, reasoning "
                "correctly that stop is excluded (exclusive upper bound) and that start "
                "defaults to 0 and step to 1.",
                [
                    lesson(
                        "counting-with-range",
                        "Counting with range()",
                        "Loop a fixed number of times and predict the first and last values.",
                        8,
                    ),
                    lesson(
                        "range-boundaries",
                        "Getting range() boundaries right",
                        "Choose start, stop and step so a loop covers exactly the intended "
                        "numbers, without off-by-one errors.",
                        8,
                        kind=PRACTICE,
                    ),
                ],
            ),
            concept(
                "while-loops",
                "While Loops",
                "Repeating while a condition holds.",
                "Write while loops whose condition eventually becomes false, and update the "
                "loop variable so the loop neither stops early nor runs forever.",
                [
                    lesson(
                        "repeating-until-done",
                        "Repeating until done",
                        "Use a while loop when the number of repetitions is not known upfront.",
                        9,
                    )
                ],
            ),
            concept(
                "break-and-continue",
                "Break and Continue",
                "Leaving a loop early or skipping an iteration.",
                "Use break to exit a loop early and continue to skip to the next iteration, "
                "and predict which statements still run.",
                [
                    lesson(
                        "controlling-a-loop",
                        "Controlling a loop",
                        "Stop searching once a match is found and skip unwanted items.",
                        7,
                    )
                ],
            ),
            concept(
                "nested-loops",
                "Nested Loops",
                "Loops inside loops.",
                "Write nested loops to process grids and combinations, and predict how many "
                "times the inner body runs.",
                [
                    lesson(
                        "loops-inside-loops",
                        "Loops inside loops",
                        "Walk rows and columns and count inner iterations.",
                        10,
                    )
                ],
            ),
        ],
    },
    {
        "slug": "functions",
        "title": "Functions",
        "description": "Package reusable behaviour into named, testable pieces.",
        "concepts": [
            concept(
                "defining-and-calling-functions",
                "Defining and Calling Functions",
                "Naming a block of code and running it on demand.",
                "Define functions with def and call them, explaining that the body only runs "
                "when the function is called.",
                [
                    lesson(
                        "your-first-function",
                        "Your first function",
                        "Move repeated code into a function and call it.",
                        8,
                    )
                ],
            ),
            concept(
                "parameters",
                "Parameters",
                "Passing data into functions.",
                "Declare parameters and pass positional and keyword arguments, matching each "
                "argument to the right parameter.",
                [
                    lesson(
                        "passing-information-in",
                        "Passing information in",
                        "Make a function flexible by giving it parameters.",
                        8,
                    )
                ],
            ),
            concept(
                "return-values",
                "Return Values",
                "Sending results back to the caller.",
                "Use return to send a value back to the caller, distinguish returning from "
                "printing, and recognise that a function without return gives None.",
                [
                    lesson(
                        "getting-results-back",
                        "Getting results back",
                        "Return a computed value and use it in an expression.",
                        9,
                    )
                ],
            ),
            concept(
                "scope",
                "Scope",
                "Where names are visible.",
                "Predict whether a name refers to a local or a global variable, and avoid "
                "relying on global state inside functions.",
                [
                    lesson(
                        "local-and-global-names",
                        "Local and global names",
                        "Trace which variable a name refers to inside and outside a function.",
                        8,
                    )
                ],
            ),
            concept(
                "default-arguments",
                "Default Arguments",
                "Optional parameters with default values.",
                "Give parameters default values so callers can omit them, and avoid mutable "
                "default values.",
                [
                    lesson(
                        "optional-parameters",
                        "Optional parameters",
                        "Add sensible defaults and call the function with and without them.",
                        7,
                    )
                ],
            ),
        ],
    },
    {
        "slug": "debugging",
        "title": "Debugging",
        "description": "Find and fix errors calmly and systematically.",
        "concepts": [
            concept(
                "syntax-errors",
                "Syntax Errors",
                "Code Python cannot parse.",
                "Recognise common syntax errors such as missing colons, unbalanced brackets "
                "and bad indentation, and fix them from the error message.",
                [
                    lesson(
                        "code-python-cannot-read",
                        "Code Python cannot read",
                        "Locate and fix syntax errors using the reported line.",
                        7,
                    )
                ],
            ),
            concept(
                "runtime-errors",
                "Runtime Errors",
                "Exceptions raised while a program runs.",
                "Identify common runtime exceptions (NameError, TypeError, ValueError, "
                "IndexError, KeyError) and explain what caused each one.",
                [
                    lesson(
                        "when-running-code-fails",
                        "When running code fails",
                        "Match an exception type to the mistake that caused it.",
                        9,
                    )
                ],
            ),
            concept(
                "logic-errors",
                "Logic Errors",
                "Programs that run but give the wrong result.",
                "Detect logic errors by comparing actual output with expected output, "
                "including wrong conditions and off-by-one mistakes.",
                [
                    lesson(
                        "wrong-answers-no-errors",
                        "Wrong answers, no error",
                        "Find the faulty condition in a program that runs but misbehaves.",
                        9,
                    )
                ],
            ),
            concept(
                "tracebacks",
                "Tracebacks",
                "Reading Python's error reports.",
                "Read a traceback from the bottom up to find the exception type, message and "
                "the line of your code that triggered it.",
                [
                    lesson(
                        "reading-a-traceback",
                        "Reading a traceback",
                        "Extract the exception, message and failing line from a traceback.",
                        8,
                    )
                ],
            ),
            concept(
                "debugging-workflow",
                "Debugging Workflow",
                "A repeatable process for finding bugs.",
                "Apply a repeatable debugging process: reproduce the problem, read the error, "
                "form a hypothesis, inspect values with print(), fix, and re-test.",
                [
                    lesson(
                        "a-debugging-routine",
                        "A debugging routine",
                        "Follow a step-by-step routine to isolate a bug.",
                        8,
                    ),
                    lesson(
                        "fix-the-broken-program",
                        "Fix the broken program",
                        "Use the routine to repair a program with several kinds of error.",
                        12,
                        kind=PRACTICE,
                    ),
                ],
            ),
        ],
    },
    {
        "slug": "python-structure",
        "title": "Python Structure",
        "description": "Organise code across files, modules and packages.",
        "concepts": [
            concept(
                "imports",
                "Imports",
                "Using code from the standard library.",
                "Import modules and specific names with import and from ... import, and use "
                "standard-library tools such as math and random.",
                [
                    lesson(
                        "using-the-standard-library",
                        "Using the standard library",
                        "Import a module and call its functions.",
                        7,
                    )
                ],
            ),
            concept(
                "modules",
                "Modules",
                "Splitting code into your own .py files.",
                "Split a program into your own modules and import functions from one file "
                "into another.",
                [
                    lesson(
                        "your-own-modules",
                        "Your own modules",
                        "Move helper functions into a separate file and import them.",
                        9,
                    )
                ],
            ),
            concept(
                "packages",
                "Packages",
                "Grouping modules into directories.",
                "Organise related modules into a package directory and import from it using "
                "dotted paths.",
                [
                    lesson(
                        "grouping-modules",
                        "Grouping modules into packages",
                        "Create a package and import modules from it.",
                        8,
                    )
                ],
            ),
            concept(
                "main-guard",
                'if __name__ == "__main__"',
                "Separating importable code from script entry points.",
                'Use if __name__ == "__main__" so a module runs its script code only when '
                "executed directly, not when imported.",
                [
                    lesson(
                        "script-or-module",
                        "Script or module?",
                        "Guard script-only code so a file can be both run and imported.",
                        6,
                    )
                ],
            ),
        ],
    },
    {
        "slug": "oop-basics",
        "title": "OOP Basics",
        "description": "Model things in your program with classes and objects.",
        "concepts": [
            concept(
                "classes-and-objects",
                "Classes and Objects",
                "Defining a class and creating instances.",
                "Define a class and create several independent objects from it, explaining the "
                "difference between a class and an instance.",
                [
                    lesson(
                        "blueprints-and-things",
                        "Blueprints and things",
                        "Create a class and instantiate objects from it.",
                        9,
                    )
                ],
            ),
            concept(
                "attributes",
                "Attributes",
                "Data stored on objects.",
                "Read and update instance attributes and predict that each object keeps its "
                "own values.",
                [
                    lesson(
                        "data-on-objects",
                        "Data on objects",
                        "Store and change information on individual objects.",
                        7,
                    )
                ],
            ),
            concept(
                "methods",
                "Methods",
                "Functions that belong to a class.",
                "Define methods that use self to read and change an object's attributes, and "
                "call them on instances.",
                [
                    lesson(
                        "behaviour-on-objects",
                        "Behaviour on objects",
                        "Add methods that act on the object's own data.",
                        9,
                    )
                ],
            ),
            concept(
                "init-method",
                "__init__",
                "Initialising new objects.",
                "Write an __init__ method that takes arguments and sets up each new object's "
                "initial attributes.",
                [
                    lesson(
                        "setting-up-new-objects",
                        "Setting up new objects",
                        "Use __init__ to give every object a valid starting state.",
                        8,
                    )
                ],
            ),
            concept(
                "basic-inheritance",
                "Basic Inheritance",
                "Reusing and specialising a class.",
                "Create a subclass that inherits attributes and methods from a parent class, "
                "override a method, and call the parent version with super().",
                [
                    lesson(
                        "specialising-a-class",
                        "Specialising a class",
                        "Extend a class and override one of its methods.",
                        10,
                    )
                ],
            ),
        ],
    },
    {
        "slug": "real-data",
        "title": "Real Data",
        "description": "Read, write and reshape data stored in files.",
        "concepts": [
            concept(
                "files",
                "Reading and Writing Files",
                "Working with text files.",
                "Read from and write to text files using with open(...) and choose the right "
                "file mode (r, w, a).",
                [
                    lesson(
                        "working-with-text-files",
                        "Working with text files",
                        "Save text to a file and read it back safely.",
                        10,
                    )
                ],
            ),
            concept(
                "paths",
                "Paths",
                "Locating files reliably.",
                "Build and inspect file paths with pathlib.Path, and check whether a file "
                "exists before using it.",
                [
                    lesson(
                        "finding-files",
                        "Finding files with pathlib",
                        "Construct paths that work regardless of where the script runs.",
                        7,
                    )
                ],
            ),
            concept(
                "json",
                "JSON",
                "Structured data as JSON.",
                "Load JSON from a file into dictionaries and lists, and save Python data back "
                "to JSON with the json module.",
                [
                    lesson(
                        "structured-data-with-json",
                        "Structured data with JSON",
                        "Round-trip nested data between Python and a JSON file.",
                        9,
                    )
                ],
            ),
            concept(
                "csv",
                "CSV",
                "Tabular data in CSV files.",
                "Read rows from a CSV file with the csv module, including a header row, and "
                "write rows back out.",
                [
                    lesson(
                        "tables-in-csv",
                        "Tables in CSV files",
                        "Read a spreadsheet-style file row by row.",
                        9,
                    )
                ],
            ),
            concept(
                "data-transformation",
                "Simple Data Transformation",
                "Filtering, aggregating and reshaping records.",
                "Filter, count, sum and group records loaded from a file to answer a concrete "
                "question about the data.",
                [
                    lesson(
                        "answering-questions-with-data",
                        "Answering questions with data",
                        "Compute totals and counts from a list of records.",
                        10,
                    ),
                    lesson(
                        "clean-and-summarise",
                        "Clean and summarise a dataset",
                        "Load a small dataset, discard invalid rows and produce a summary.",
                        15,
                        kind=PRACTICE,
                    ),
                ],
            ),
        ],
    },
    {
        "slug": "python-developer",
        "title": "Python Developer",
        "description": "Plan, build, test and finish a complete Python project.",
        "concepts": [
            concept(
                "project-planning",
                "Project Planning",
                "Turning an idea into a buildable plan.",
                "Break a project idea into small, testable steps with clear inputs and outputs "
                "before writing code.",
                [
                    lesson(
                        "planning-a-project",
                        "Planning a project",
                        "Write a step-by-step plan for a small command-line tool.",
                        10,
                    )
                ],
            ),
            concept(
                "build-and-integration",
                "Build and Integration",
                "Assembling working pieces into one program.",
                "Build a program incrementally by combining functions, modules and data files, "
                "running it after each step.",
                [
                    lesson(
                        "building-step-by-step",
                        "Building step by step",
                        "Grow a program one working piece at a time.",
                        15,
                    )
                ],
            ),
            concept(
                "testing-and-refactoring",
                "Testing and Refactoring",
                "Checking behaviour and improving structure safely.",
                "Write simple assert-based tests for functions and refactor code while keeping "
                "those tests passing.",
                [
                    lesson(
                        "testing-your-code",
                        "Testing your code",
                        "Check function results with assert and improve code safely.",
                        12,
                    )
                ],
            ),
            concept(
                "final-project",
                "Final Project",
                "An end-to-end project using the whole Python Foundations toolkit.",
                "Plan, build, test and present a complete small Python program that reads "
                "data, processes it with functions and classes, and reports results.",
                [
                    lesson(
                        "project-brief",
                        "Project brief",
                        "Understand the final project requirements and plan the work.",
                        8,
                    ),
                    lesson(
                        "build-your-project",
                        "Build your project",
                        "Deliver a working, tested program that meets the brief.",
                        45,
                        kind=CHALLENGE,
                    ),
                ],
            ),
        ],
    },
]

# (skill, prerequisite) — the default MVP learning path.
SKILL_PREREQUISITES = [
    ("variables", "start"),
    ("decisions", "variables"),
    ("collections", "decisions"),
    ("loops", "collections"),
    ("functions", "loops"),
    ("debugging", "functions"),
    ("python-structure", "debugging"),
    ("oop-basics", "python-structure"),
    ("real-data", "oop-basics"),
    ("python-developer", "real-data"),
]

# (concept, prerequisite) as "skill-slug/concept-slug". The graph must stay acyclic; model
# validation rejects any edge that would close a cycle.
CONCEPT_PREREQUISITES = [
    # Start
    ("start/print-and-output", "start/running-python"),
    ("start/comments", "start/running-python"),
    ("start/expressions", "start/print-and-output"),
    # Variables
    ("variables/variables-and-values", "start/expressions"),
    ("variables/basic-types", "variables/variables-and-values"),
    ("variables/naming", "variables/variables-and-values"),
    ("variables/user-input", "variables/variables-and-values"),
    ("variables/user-input", "start/print-and-output"),
    ("variables/type-conversion", "variables/basic-types"),
    ("variables/type-conversion", "variables/user-input"),
    # Decisions
    ("decisions/booleans", "variables/basic-types"),
    ("decisions/comparison-operators", "variables/basic-types"),
    ("decisions/if-statements", "decisions/booleans"),
    ("decisions/if-statements", "decisions/comparison-operators"),
    ("decisions/elif-and-else", "decisions/if-statements"),
    ("decisions/logical-operators", "decisions/booleans"),
    # Collections
    ("collections/list-basics", "variables/variables-and-values"),
    ("collections/indexing-and-slicing", "collections/list-basics"),
    ("collections/list-mutation", "collections/list-basics"),
    ("collections/tuples", "collections/indexing-and-slicing"),
    ("collections/dictionaries", "collections/list-basics"),
    ("collections/sets", "collections/list-basics"),
    # Loops
    ("loops/for-loops", "collections/list-basics"),
    ("loops/for-loops", "decisions/if-statements"),
    ("loops/range", "loops/for-loops"),
    ("loops/while-loops", "decisions/comparison-operators"),
    ("loops/while-loops", "decisions/if-statements"),
    ("loops/break-and-continue", "loops/for-loops"),
    ("loops/break-and-continue", "loops/while-loops"),
    ("loops/nested-loops", "loops/for-loops"),
    # Functions
    ("functions/defining-and-calling-functions", "variables/variables-and-values"),
    ("functions/parameters", "functions/defining-and-calling-functions"),
    ("functions/return-values", "functions/defining-and-calling-functions"),
    ("functions/scope", "functions/parameters"),
    ("functions/default-arguments", "functions/parameters"),
    # Debugging
    ("debugging/runtime-errors", "variables/type-conversion"),
    ("debugging/logic-errors", "decisions/comparison-operators"),
    ("debugging/logic-errors", "loops/range"),
    ("debugging/tracebacks", "debugging/runtime-errors"),
    ("debugging/tracebacks", "functions/return-values"),
    ("debugging/debugging-workflow", "debugging/syntax-errors"),
    ("debugging/debugging-workflow", "debugging/runtime-errors"),
    ("debugging/debugging-workflow", "debugging/logic-errors"),
    ("debugging/debugging-workflow", "debugging/tracebacks"),
    # Python Structure
    ("python-structure/imports", "functions/defining-and-calling-functions"),
    ("python-structure/modules", "python-structure/imports"),
    ("python-structure/packages", "python-structure/modules"),
    ("python-structure/main-guard", "python-structure/modules"),
    # OOP Basics
    ("oop-basics/classes-and-objects", "functions/defining-and-calling-functions"),
    ("oop-basics/attributes", "oop-basics/classes-and-objects"),
    ("oop-basics/methods", "oop-basics/classes-and-objects"),
    ("oop-basics/methods", "functions/parameters"),
    ("oop-basics/init-method", "oop-basics/classes-and-objects"),
    ("oop-basics/init-method", "oop-basics/attributes"),
    ("oop-basics/basic-inheritance", "oop-basics/classes-and-objects"),
    ("oop-basics/basic-inheritance", "oop-basics/methods"),
    # Real Data
    ("real-data/files", "real-data/paths"),
    ("real-data/files", "loops/for-loops"),
    ("real-data/paths", "python-structure/imports"),
    ("real-data/json", "real-data/files"),
    ("real-data/json", "collections/dictionaries"),
    ("real-data/csv", "real-data/files"),
    ("real-data/csv", "collections/list-basics"),
    ("real-data/data-transformation", "real-data/json"),
    ("real-data/data-transformation", "real-data/csv"),
    ("real-data/data-transformation", "functions/return-values"),
    # Python Developer
    ("python-developer/project-planning", "functions/return-values"),
    ("python-developer/build-and-integration", "python-developer/project-planning"),
    ("python-developer/build-and-integration", "python-structure/modules"),
    ("python-developer/testing-and-refactoring", "python-developer/build-and-integration"),
    ("python-developer/testing-and-refactoring", "debugging/debugging-workflow"),
    ("python-developer/final-project", "python-developer/project-planning"),
    ("python-developer/final-project", "python-developer/build-and-integration"),
    ("python-developer/final-project", "python-developer/testing-and-refactoring"),
]
