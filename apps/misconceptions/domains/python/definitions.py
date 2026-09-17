"""Python misconception catalog: every code the Python exercise packs may tag."""

from apps.misconceptions.definitions import MisconceptionDefinition

DOMAIN = "python"

# (code, category, title, description)
CATALOG = (
    # syntax and program structure
    (
        "comment-syntax",
        "syntax",
        "Writes notes without a comment marker",
        "Expects plain English lines to be ignored, instead of starting them with #.",
    ),
    (
        "comment-scope",
        "syntax",
        "Misjudges what a comment hides",
        "Is unsure which part of a line Python ignores after #.",
    ),
    (
        "syntax-missing-comma",
        "syntax",
        "Leaves out commas between arguments",
        "Writes values side by side where Python needs commas to separate them.",
    ),
    (
        "syntax-unclosed-bracket",
        "syntax",
        "Leaves a bracket unclosed",
        "Opens a bracket, parenthesis or quote without closing it.",
    ),
    (
        "invalid-identifier",
        "syntax",
        "Uses an invalid variable name",
        "Names variables in ways Python forbids, such as starting with a digit.",
    ),
    (
        "indentation-block",
        "syntax",
        "Misunderstands Python block indentation",
        "Does not use indentation to mark which lines belong to an if, loop or function.",
    ),
    (
        "execution-order",
        "syntax",
        "Misreads execution order",
        "Expects statements to run in an order other than top to bottom.",
    ),
    (
        "import-syntax",
        "structure",
        "Misuses import statements",
        "Is unsure how import and from ... import name modules, packages and objects.",
    ),
    (
        "main-guard",
        "structure",
        "Misunderstands the main guard",
        'Writes or reads if __name__ == "__main__" incorrectly.',
    ),
    (
        "decomposition",
        "structure",
        "Struggles to split a problem into parts",
        "Keeps work in one block instead of separating it into clear, reusable steps.",
    ),
    (
        "duplicated-code",
        "structure",
        "Repeats code instead of reusing it",
        "Copies the same logic rather than extracting a function.",
    ),
    # values, variables and operators
    (
        "variable-reassignment",
        "values",
        "Misreads variable reassignment",
        "Expects a variable to keep an earlier value after it has been reassigned.",
    ),
    (
        "expression-not-assigned",
        "values",
        "Expects an expression to update a variable",
        "Writes a calculation without assigning its result, expecting the variable to change.",
    ),
    (
        "string-concatenation",
        "values",
        "Confuses joining text with adding numbers",
        "Expects + on strings that look like numbers to add them arithmetically.",
    ),
    (
        "input-returns-string",
        "values",
        "Forgets input() returns text",
        "Uses the result of input() as a number without converting it.",
    ),
    (
        "int-conversion",
        "values",
        "Misunderstands int() conversion",
        "Expects int() to accept any numeric-looking text, such as a decimal string.",
    ),
    (
        "type-mismatch",
        "values",
        "Mixes incompatible types",
        "Combines text and numbers in one operation without converting either.",
    ),
    (
        "floor-division",
        "values",
        "Confuses division operators",
        "Mixes up /, // and % and what each returns.",
    ),
    (
        "operator-precedence",
        "values",
        "Misjudges operator precedence",
        "Expects operators to apply left to right regardless of precedence.",
    ),
    (
        "truthiness",
        "values",
        "Misunderstands truthy and falsy values",
        "Is unsure which values count as true or false in a condition.",
    ),
    # decisions
    (
        "comparison-direction",
        "decisions",
        "Reverses comparison direction",
        "Uses < where > is needed, or the other way round.",
    ),
    (
        "comparison-boundary",
        "decisions",
        "Confuses strict and inclusive comparison",
        "Uses > or < where >= or <= is needed at the boundary value, or the reverse.",
    ),
    (
        "or-comparison",
        "decisions",
        "Shortens or-conditions incorrectly",
        "Writes x == a or b, expecting it to compare x with both values.",
    ),
    (
        "elif-order",
        "decisions",
        "Misorders elif branches",
        "Forgets that only the first true branch runs, so broad conditions hide later ones.",
    ),
    (
        "case-sensitive-comparison",
        "decisions",
        "Forgets comparisons are case-sensitive",
        "Expects text with different capitalisation to compare as equal.",
    ),
    # loops
    (
        "range-default-start",
        "loops",
        "Forgets range starts at 0",
        "Expects range(n) to start at 1 instead of 0.",
    ),
    (
        "range-exclusive-stop",
        "loops",
        "Treats range stop as inclusive",
        "Expects range to include its stop value, which it always excludes.",
    ),
    (
        "range-step",
        "loops",
        "Misunderstands range step",
        "Leaves out the step, or uses a step with the wrong sign, when counting in steps.",
    ),
    (
        "off-by-one",
        "loops",
        "Off-by-one error",
        "Stops, starts or counts one position too early or too late.",
    ),
    (
        "loop-condition",
        "loops",
        "Uses the wrong loop stopping condition",
        "Writes a while condition that stops too early, too late or never.",
    ),
    (
        "infinite-while",
        "loops",
        "Loop condition never progresses",
        "Writes a while loop whose condition never becomes false, usually because nothing "
        "inside it moves towards the end.",
    ),
    (
        "loop-accumulator",
        "loops",
        "Mishandles a running total",
        "Resets or updates an accumulator in the wrong place relative to the loop.",
    ),
    (
        "loop-variable",
        "loops",
        "Misuses the loop variable",
        "Is unsure what the loop variable holds on each pass.",
    ),
    (
        "break-vs-continue",
        "loops",
        "Confuses break and continue",
        "Mixes up ending the loop (break) with skipping to the next pass (continue).",
    ),
    (
        "nested-loop-count",
        "loops",
        "Miscounts nested loop repetitions",
        "Does not multiply the passes of an inner loop by those of the outer loop.",
    ),
    (
        "nested-loop-indentation",
        "loops",
        "Misplaces code between nested loops",
        "Indents a statement into the wrong loop level.",
    ),
    (
        "nested-loop-variables",
        "loops",
        "Mixes up nested loop variables",
        "Confuses which variable belongs to the inner and outer loop.",
    ),
    # collections
    (
        "zero-based-index",
        "collections",
        "Forgets indexes start at 0",
        "Counts positions from 1 when Python indexes from 0.",
    ),
    (
        "last-index",
        "collections",
        "Uses len() as the last index",
        "Indexes with len(items), one past the last valid position.",
    ),
    (
        "slice-bounds",
        "collections",
        "Misreads slice bounds",
        "Expects a slice to include its end index, or misplaces its start.",
    ),
    (
        "hard-coded-length",
        "collections",
        "Hard-codes a collection size",
        "Writes a fixed number instead of using len() for data that can change.",
    ),
    (
        "list-aliasing",
        "collections",
        "Misunderstands shared list references",
        "Expects assigning a list to a new name to copy it.",
    ),
    (
        "mutation-vs-new-list",
        "collections",
        "Confuses in-place changes with new lists",
        "Expects methods such as list.sort() to return a new list.",
    ),
    (
        "tuple-immutability",
        "collections",
        "Tries to change a tuple",
        "Expects tuples to be modifiable like lists.",
    ),
    (
        "missing-key",
        "collections",
        "Reads dictionary keys that may be missing",
        "Indexes a dictionary without handling keys that are not there.",
    ),
    # functions
    (
        "definition-vs-call",
        "functions",
        "Confuses defining and calling a function",
        "Expects def to run the function, or forgets the parentheses when calling it.",
    ),
    (
        "arguments-vs-parameters",
        "functions",
        "Confuses arguments and parameters",
        "Mixes up the names in a definition with the values passed in a call.",
    ),
    (
        "default-arguments",
        "functions",
        "Misunderstands default arguments",
        "Is unsure when a parameter's default value is used or overridden.",
    ),
    (
        "mutable-default",
        "functions",
        "Uses a mutable default argument",
        "Expects a default list or dict to be recreated on every call.",
    ),
    (
        "print-vs-return",
        "functions",
        "Confuses print with return",
        "Prints a result where the function should give it back to the caller.",
    ),
    (
        "missing-return",
        "functions",
        "Forgets to return a value",
        "Computes a result but lets the function return None.",
    ),
    (
        "local-scope",
        "functions",
        "Misunderstands local scope",
        "Expects variables created inside a function to exist outside it, or the reverse.",
    ),
    (
        "initial-value",
        "functions",
        "Chooses a wrong starting value",
        "Starts a search or total from a value that breaks some inputs.",
    ),
    # objects
    (
        "class-vs-instance",
        "objects",
        "Confuses a class with its instances",
        "Uses the class itself where an object created from it is needed.",
    ),
    (
        "init",
        "objects",
        "Misunderstands __init__",
        "Is unsure when __init__ runs or what it should set up.",
    ),
    (
        "self",
        "objects",
        "Misuses self",
        "Leaves out self from a method, or forgets it when storing attributes.",
    ),
    (
        "instance-attributes",
        "objects",
        "Expects objects to share attributes",
        "Expects a change to one object's attribute to affect other objects.",
    ),
    (
        "method-state",
        "objects",
        "Loses track of an object's state",
        "Does not follow how methods change an object's attributes over several calls.",
    ),
    (
        "inheritance-lookup",
        "objects",
        "Misreads inheritance lookup",
        "Is unsure whether a subclass or its parent method runs.",
    ),
    (
        "attribute-typo",
        "objects",
        "Creates attributes by mistyping names",
        "Does not notice that assigning to a misspelled attribute silently creates a new one.",
    ),
    # files and data
    (
        "file-modes",
        "data",
        "Confuses file modes",
        "Mixes up reading, writing (which replaces the file) and appending.",
    ),
    (
        "newline-handling",
        "data",
        "Mishandles line endings",
        "Forgets that lines read from a file keep their trailing newline.",
    ),
    (
        "csv-header-row",
        "data",
        "Treats the CSV header as data",
        "Processes the header row as if it were a record.",
    ),
    (
        "csv-values-are-strings",
        "data",
        "Forgets CSV values are text",
        "Uses CSV fields as numbers without converting them.",
    ),
    (
        "json-string-vs-data",
        "data",
        "Confuses JSON text with Python data",
        "Indexes a JSON string without parsing it, or treats parsed data as text.",
    ),
    (
        "json-structure",
        "data",
        "Misreads nested JSON structure",
        "Is unsure how lists and objects nest inside parsed JSON.",
    ),
    # debugging and testing
    (
        "reading-traceback",
        "debugging",
        "Misreads a traceback",
        "Looks at the wrong part of a traceback instead of the final error and its line.",
    ),
    (
        "error-kinds",
        "debugging",
        "Confuses kinds of errors",
        "Mixes up syntax errors, runtime exceptions and wrong results.",
    ),
    (
        "debugging-process",
        "debugging",
        "Debugs without a method",
        "Changes code at random instead of checking values step by step.",
    ),
    (
        "symptom-vs-cause",
        "debugging",
        "Fixes the symptom instead of the cause",
        "Hides an error where it appears rather than correcting what produced it.",
    ),
    (
        "weak-tests",
        "debugging",
        "Writes tests that miss edge cases",
        "Chooses checks that pass even when the code is wrong at the boundaries.",
    ),
)

DEFINITIONS = tuple(
    MisconceptionDefinition(
        code=code, title=title, description=description, domain=DOMAIN, category=category
    )
    for code, category, title, description in CATALOG
)
