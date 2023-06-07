from rich.logging import RichHandler
from rich import print
import sqlite3
import logging
import json5
import sys

# Rich logging
FORMAT = "%(message)s"
logging.basicConfig(
    level="NOTSET", format=FORMAT, datefmt="[%X]", handlers=[RichHandler(markup=True)]
)
log = logging.getLogger("rich")
DEBUG_PRINTS = "-d" in sys.argv
CHECK_BOUNDS = "-l" in sys.argv and "-u" in sys.argv

print("[bold blue]SQLHammer version 1.0.0, (c) 2023 Ethan Hanlon.[/bold blue]\n\n")

# Help message
if "-h" in sys.argv:
    print(
        """
        [bold]Usage:[/bold]
        python main.py [bold]-d[/bold] [bold]-l[/bold] [bold]-u[/bold] [bold]-h[/bold]

        [bold]Arguments:[/bold]
        [bold]-d[/bold] Debug prints
        [bold]-l[/bold] Check lower bounds
        [bold]-u[/bold] Check upper bounds
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
    COLUMNS = [f"{i} {COLUMNS[i]}" for i in COLUMNS] # FIXME: TypeError: list indives must be integers or slices, not str
    COLUMNS = ", ".join(COLUMNS)

    CONSTANTS = settings["constants"]
    EQUATIONS = settings["equations"]
    TEMPLATE = settings["template"]
    TEMPLATE = [f"{i} {TEMPLATE[i]}" for i in TEMPLATE]
    TEMPLATE = ", ".join(TEMPLATE)
except KeyError:
    MISSING = []
    for i in ["database", "table", "columns", "constants", "equations", "template"]:
        if i not in settings:
            MISSING.append(i)
    log.fatal("Settings is misconfigured. Missing keys: " + ", ".join(MISSING))
    sys.exit(1)

# Bounds (if present)
if CHECK_BOUNDS:
    try:
        global LOWER_BOUND, UPPER_BOUND
        LOWER_BOUND = sys.argv[sys.argv.index("-l") + 1]
        UPPER_BOUND = sys.argv[sys.argv.index("-u") + 1]

        if not LOWER_BOUND.isnumeric() or not UPPER_BOUND.isnumeric():
            log.error("Bounds must be numeric.")
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

# Functions
def inputBounds():
    global LOWER_BOUND, UPPER_BOUND
    LOWER_BOUND = input("Enter lower bound: ")
    UPPER_BOUND = input("Enter upper bound: ")
    if not LOWER_BOUND.isnumeric() or not UPPER_BOUND.isnumeric():
        log.error("Bounds must be numeric.")
        inputBounds()

# Main

"""
Example settings.jsonc:
{
    "db": "db.batthealth", // The database to write to
    "table": "batt", // The table to write to
    "columns": ["time", "cycle", "amperage"], // The columns to write to
    "constants": { // Constants for equations
        "L": 20,
        "t0": 2,
        "k": 0.1
    },
    "equations": { // Numeric equations to write
        "LINEAR": {
            "variables": ["t"],
            "equation": "t"
        },
        "SIGMOID": {
            "variables": ["L", "t", "t0", "k"],
            "equation": "L / (1 + e^(-k(t - t0)))"
        }
    },
    "template": { // The template for the dummy data to write
        "time": "EQUATION_TIME",
        "cycle": 1,
        "amperage": "EQUATION_SIGMOID"
    }
}

Example output if lower bound is 0 and upper bound is 5:
time, cycle, amperage
0, 1, 0.5
1, 1, 0.52497918747894
2, 1, 0.54983399731248
3, 1, 0.574442516811659
4, 1, 0.598687660112452
5, 1, 0.622459331201854
"""

if CHECK_BOUNDS: inputBounds()

log.info("Everything looks OK. Starting...")

for i in range(int(LOWER_BOUND), int(UPPER_BOUND) + 1):
    for j in CONSTANTS:
        exec(f"{j} = {CONSTANTS[j]}")
    for j in EQUATIONS:
        for k in EQUATIONS[j]["variables"]:
            exec(f"{k} = {i}")
        exec(f"{j} = {EQUATIONS[j]['equation']}")
    for j in TEMPLATE:
        exec(f"{j} = {TEMPLATE[j]}")
    c.execute(f"INSERT INTO {TABLE} VALUES ({TEMPLATE})")
    conn.commit()
    if DEBUG_PRINTS: print(f"INSERT INTO {TABLE} VALUES ({TEMPLATE})")

log.info("Done.")
