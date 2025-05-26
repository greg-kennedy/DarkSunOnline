#!/bin/env python3

"""
DSOServer - reverse engineered Dark Sun Online: Crimson Sands server
Greg Kennedy, 2025

This software is released under the GNU AGPL 3.0.  See file LICENSE for more information.
"""

import logging
from argparse import ArgumentParser
from pathlib import Path

# need at least one provider for persistent storage
#  sqlite3 is fine, you could replace this with something else
from DSOServer.Database import Sqlite3

# the guts of a running server
from DSOServer.Server import Server

# Read CLI args we want to use to set up everything
parser = ArgumentParser(
    prog="DSOServer",
    description="Run the recreated server program for Dark Sun Online: Crimson Sands.",
    epilog="More information is available at the project webpage: https://github.com/greg-kennedy/DarkSunOnline",
)
parser.add_argument(
    "-p",
    "--port",
    help="TCP port number the server will listen on (default: %(default)s)",
    type=int,
    default=14902,
)
parser.add_argument(
    "-a",
    "--address",
    help="Address to listen on ('0.0.0.0' or blank for any) (default: %(default)s)",
    default="",
)
parser.add_argument(
    "-d",
    "--database",
    help="Path to sqlite3 database for world / player state (default: %(default)s)",
    type=Path,
    default="server.db",
)
parser.add_argument(
    "-l",
    "--level",
    help="Log level of server process",
    choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
    default="NOTSET",
)
args = parser.parse_args()

# set up logger level
logging.basicConfig(level=logging.getLevelName(args.level))

# open the db
with Sqlite3(args.database) as db:
    # Run the server!
    Server((args.address, args.port), db).run()
