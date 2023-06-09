from rich.logging import RichHandler
from rich import print
import sqlite3
import random
import logging
import json5
import copy
import math
import sys

# Rich logging
FORMAT = "%(message)s"
logging.basicConfig(
    level="NOTSET", format=FORMAT, datefmt="[%X]", handlers=[RichHandler(markup=True)]
)
log = logging.getLogger("rich")
DEBUG_PRINTS = "-d" in sys.argv
BOUNDS_SUPPLIED = "-l" in sys.argv and "-u" in sys.argv

print("[bold blue]SQLHammer version 1.0.0, (c) 2023 Ethan Hanlon.[/bold blue]\n\n")

# Help message
if "-h" in sys.argv:
    print(
        """
        [bold]Usage:[/bold]
        python main.py [bold]-l[/bold] [italic]<lower bound>[/italic] [bold]-u[/bold] [italic]<upper bound>[/italic] [bold]-d[/bold] [bold]-h[/bold]

        [bold]Arguments:[/bold]
        [bold]-l[/bold] Lower bound
        [bold]-u[/bold] Upper bound
        [bold]-d[/bold] Debug prints
        [bold]-h[/bold] Help message
        """
    )
    sys.exit(0)

# Settings
try:
    with open("./settings.jsonc") as f:
        settings = json5.load(f)
except FileNotFoundError:
    log.fatal("settings.jsonc not found.")
    sys.exit(1)

try:
    global DB, TABLE, COLUMNS, CONSTANTS, EQUATIONS, TEMPLATE
    DB = settings["database"]
    TABLE = settings["table"]
    COLUMNS = settings["columns"]
    COLUMNS = [f"{COLUMNS[i]}" for i in range(0,len(COLUMNS))]
    COLUMNS = ", ".join(COLUMNS)

    CONSTANTS = settings["constants"]
    EQUATIONS = settings["equations"]
    TEMPLATE = settings["template"]
    TEMPLATE = [f"{i} {TEMPLATE[i]}" for i in TEMPLATE]

    if DEBUG_PRINTS:
        log.debug(f"DB: {DB}")
        log.debug(f"TABLE: {TABLE}")
        log.debug(f"COLUMNS: {COLUMNS}")
        log.debug(f"CONSTANTS: {CONSTANTS}")
except KeyError:
    MISSING = []
    for i in ["database", "table", "columns", "constants", "equations", "template"]:
        if i not in settings: MISSING.append(i)
    log.fatal("Settings is misconfigured. Missing keys: " + ", ".join(MISSING))
    sys.exit(1)

# Bounds

def isValidBounds(lower, upper):
    if not lower.isnumeric() or not upper.isnumeric():
        log.error("Bounds must be numeric.")
        return False
    if not isinstance(int(lower), int) or not isinstance(int(upper), int):
        log.error("Bounds must be integers.")
        return False
    if int(lower) > int(upper) or int(lower) == int(upper):
        log.error("Lower bound must be less than upper bound.")
        return False
    return True

def inputBounds():        
    global LOWER_BOUND, UPPER_BOUND
    LOWER_BOUND = input("Enter lower bound: ")
    UPPER_BOUND = input("Enter upper bound: ")
    if not isValidBounds(LOWER_BOUND, UPPER_BOUND):
        inputBounds()

if BOUNDS_SUPPLIED:
    try:
        global LOWER_BOUND, UPPER_BOUND
        LOWER_BOUND = sys.argv[sys.argv.index("-l") + 1]
        UPPER_BOUND = sys.argv[sys.argv.index("-u") + 1]

        if not isValidBounds(LOWER_BOUND,  UPPER_BOUND):
            log.info("Hint: check your command line arguments.")
            sys.exit(1)
    except IndexError:
        log.fatal("Bounds not specified.")
        log.info("Hint: python main.py -l <lower bound> -u <upper bound>")
        sys.exit(1)

# Database
try:
    global conn, c
    conn = sqlite3.connect(settings["database"])
    c = conn.cursor()
    c.execute(f"CREATE TABLE IF NOT EXISTS {TABLE} ({COLUMNS})")
    conn.commit()
except sqlite3.OperationalError:
    log.fatal("Something went wrong with the database. Make sure sqlite is installed and working properly.")
    sys.exit(1)

# Main

"""
Example settings.jsonc:
{
    "db": "db.batthealth", // The database to write to
    "table": "batt", // The table to write to
    "columns": ["time", "cycle", "amperage"], // The columns to write to
    "column_types": ["REAL", "INTEGER", "REAL"], // The types of the columns to write to. Must be one-to-one with columns.

    "constants": { // Constants for equations
        "L": 20,
        "t0": 2,
        "k": 0.1
    },
    "equations": { // Numeric equations to write
        "LINEAR": {
            "variables": ["t"],
            "equation": "t",
            "variance"L 0
        },
        "SIGMOID": {
            "variables": ["L", "t", "t0", "k"],
            "equation": "L / ((1 + math.e)**(-k*(t - t0)))",
            "variance": 0.5 // The variance to add to the equation
        }
    },
    "template": { // The template for the dummy data to write
        "time": "EQUATION_TIME",
        "cycle": 1,
        "amperage": "EQUATION_SIGMOID"
    }
}

Example output if lower bound is 0 and upper bound is 5 (without factoring in variance):
time, cycle, amperage
0, 1, 10.0
1, 1, 10.5
2, 1, 10.997
3, 1, 11.489
4, 1, 11.974
5, 1, 12.449
"""

if not BOUNDS_SUPPLIED: inputBounds()

log.info("Everything looks OK. Starting...")

# Constants and equations
if DEBUG_PRINTS: log.debug("CONSTANTS:")
for j in CONSTANTS:
    exec(f"{j} = {CONSTANTS[j]}")
    if DEBUG_PRINTS: log.debug(f"{j} = {CONSTANTS[j]}")

if DEBUG_PRINTS: log.debug("EQUATIONS:")
for j in EQUATIONS:
    exec(f"{j} = {EQUATIONS[j]}")
    if DEBUG_PRINTS: log.debug(f"{j} = {EQUATIONS[j]}")

LINEAR_FROM = {}

# TODO: Increment inside this function (as it is functions must increment themselves)
def doLinear(key, doFrom):
    if key not in LINEAR_FROM:
        # if not isinstance(doFrom, int): FIXME: Zero is not an integer???
        #     log.fatal(f"Invalid linear value for {key}. Must be an integer.")
        #     sys.exit(1)
        LINEAR_FROM[key] = int(doFrom)
    
    # make value available in global scope
    exec(f"{key} = {int(LINEAR_FROM[key])}")
    return int(LINEAR_FROM[key])

# Process template line

exec_globals = {'math': math, 'random': random}
# FIXME: The big o of this is probably terrible
for i in CONSTANTS:
    exec_globals[i] = CONSTANTS[i]
for i in EQUATIONS:
    exec_globals[i] = EQUATIONS[i]
for i in LINEAR_FROM:
    exec_globals[i] = LINEAR_FROM[i]

def processTemplateLine(key, value):
    # line is a string that correlates to the value of the key/value pair
    # If the value starts with EQUATION_x, replace it with the value of the equation
    # If the value starts with LINEAR_FROM_x, increment the value by 1 each time you see it
    # If the value starts with CONSTANT_x, replace it with the constant
    # Any other value should be left alone
    
    exec_locals = {}


    if value.startswith("EQUATION_"):
        # Get the equation name
        EQUATION_MAP = value.split("_")[1]
        equation = EQUATIONS[EQUATION_MAP]["equation"]
        VARIANCE = EQUATIONS[EQUATION_MAP]["variance"]
        VARIABLES = EQUATIONS[EQUATION_MAP]["variables"]
        # Replace the variables with their values
        for i in VARIABLES:
            # If the variable is not defined as a constant, define it as a variable
            if i not in CONSTANTS:
                # make it linear
                doLinear(i, 0)
                exec(f"{i} = {LINEAR_FROM[i]}", exec_globals, exec_locals)
                LINEAR_FROM[i] += 1

            exec(f"{i} = {i}", exec_globals, exec_locals) # This call is necessary to make the variable available to the exec() call below
            equation = equation.replace(i, f"{i}")
        print(exec_locals)
        print(f"Equation: {equation}")
        exec(f"line = {equation}", exec_globals, exec_locals) # Substitute equation
        exec(f"line += random.uniform(-{VARIANCE}, {VARIANCE})", exec_globals, exec_locals) # Variance

    elif value.startswith("LINEAR_FROM_"):
        exec(f"line = {doLinear(key, value.split('_')[2])}", exec_globals, exec_locals)
        # Increment the variable by 1
        LINEAR_FROM[key] += 1

    elif value.startswith("CONSTANT_"):
        # Get the constant name
        constant = value.split("_")[1]
        # Replace the constant with its value
        exec(f"line = {CONSTANTS[constant]}", exec_globals, exec_locals)

    else:
        # Return the value as-is
        exec(f"line = {value}", exec_globals, exec_locals)


    return exec_locals["line"]

# Template

for i in range(int(LOWER_BOUND), int(UPPER_BOUND) + 1):
    # Process the template
    TEMPLATE_COPY = copy.deepcopy(TEMPLATE)
    
    for j in TEMPLATE:
        # Get the key/value pair
        key = j.split(" ")[0]
        value = j.split(" ")[1]
        # Process the value
        value = processTemplateLine(key, value)
        # Replace the value in the template
        if DEBUG_PRINTS: log.debug(f"Template: {key} = {value}")
        TEMPLATE_COPY[TEMPLATE.index(j)] = f"{value}"
    
    # Write the template to the database
    TEMPLATE_COPY = ", ".join(TEMPLATE_COPY)
    if DEBUG_PRINTS: log.debug(f"INSERT INTO {TABLE} ({COLUMNS}) VALUES ({TEMPLATE_COPY})")
    c.execute(f"INSERT INTO {TABLE} ({COLUMNS}) VALUES ({TEMPLATE_COPY})")
    conn.commit()

log.info("Done.")
