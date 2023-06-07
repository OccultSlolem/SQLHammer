# SQLHammer
A dummy data generator for SQL. Currently only works with SQLite.

You can input equations and have this software plot them out into a table between bounds, which are fed in either by being prompted by the program, or inputting them in as command line arguments.

Usage:
``python3 main.py [-l lower bound] [-u upper bound] [-h] [-d]``

```
-l: Lower bound. Must be a number.
-u: Upper bound. Must be a number.
-h: Help message.
-d: Enable debug logging.
```