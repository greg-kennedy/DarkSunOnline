#!/bin/env python3

"""
manage.py - Edit login details for sqlite3 server database
Greg Kennedy, 2025

This software is released under the GNU AGPL 3.0.  See file LICENSE for more information.
"""
import sqlite3
from argparse import ArgumentParser
from contextlib import closing
from pathlib import Path
from sys import exit

# Read CLI args we want to use to set up everything
parser = ArgumentParser(
    prog="manage.py",
    description="""
    Edit user login information for DSOServer persistent database.

    manage.py requires one --action argument to operate.  Valid actions are:

    * list -   List all usernames in the login table.

    * add -    Add a user.  Requires a --username and --password argument.
               Will throw an exception if the user already exists.

    * change - Change password for a user.  Requires a --username and --password argument.
               Will throw an exception if the user does not exist.

    * delete - Delete a user.  Requires a --username argument.
               Will throw an exception if the user did not exist.

    * check  - Check if a password matches the specified username.
               Requires a --username and --password argument.
               If correct, prints "1" and returns 1 exit code.
               Otherwise, prints "0" and returns 0.
    """,
    epilog="More information is available at the project webpage: https://github.com/greg-kennedy/DarkSunOnline",
)
parser.add_argument(
    "-d",
    "--database",
    help="Path to sqlite3 database for world / player state (default: %(default)s)",
    type=Path,
    default="server.db",
)
parser.add_argument(
    "-a",
    "--action",
    help="Action to take.  See help (-h) for more details.",
    type=str.lower,
    choices=["list", "add", "change", "delete", "check"],
    default="list",
)
parser.add_argument(
    "-u", "--username", help="Username (required for some actions)", type=str
)
parser.add_argument(
    "-p", "--password", help="Password (required for some actions)", type=str
)
args = parser.parse_args()

# open the db
with closing(
    sqlite3.connect(args.database, detect_types=sqlite3.PARSE_DECLTYPES)
) as connection:
    connection.execute("PRAGMA foreign_keys=1")

    # make requested change
    try:
        if args.action == "list":
            if args.username or args.password:
                raise ValueError(
                    "--username and --password --password cannot be used with --action list"
                )

            with connection:
                result = connection.execute(
                    "SELECT username FROM login ORDER BY username"
                ).fetchall()

            for row in result:
                print(",".join(row))

        elif args.action == "add":
            if not (args.username and args.password):
                raise ValueError("--username and --password required with --action add")

            try:
                with connection:
                    connection.execute(
                        "INSERT INTO login(username, password) VALUES(?, ?)",
                        (args.username, args.password),
                    )
            except sqlite3.IntegrityError:
                raise ValueError("username already exists")

        elif args.action == "change":
            if not (args.username and args.password):
                raise ValueError(
                    "--username and --password required with --action change"
                )

            with connection:
                connection.execute(
                    "UPDATE login SET password=? WHERE username=?",
                    (args.password, args.username),
                )

            if not connection.total_changes:
                raise ValueError("username not found in login table")

        elif args.action == "delete":
            if not args.username:
                raise ValueError("--username required with --action delete")
            elif args.password:
                raise ValueError("--password cannot be used with --action delete")

            with connection:
                connection.execute(
                    "DELETE FROM login WHERE username=?", (args.username,)
                )

            if not connection.total_changes:
                raise ValueError("username not found in login table")

        elif args.action == "check":
            if not (args.username and args.password):
                raise ValueError(
                    "--username and --password required with --action check"
                )

            with connection:
                result = connection.execute(
                    "SELECT EXISTS (SELECT * FROM login WHERE username=? AND password=?)",
                    (args.username, args.password),
                ).fetchone()[0]

            print(result)

            exit(result)

    except ValueError as e:
        print(e)
        exit(1)
