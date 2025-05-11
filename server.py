#!/bin/env python3
from argparse import ArgumentParser
from pathlib import Path
from DSOServer.server import Server

import logging

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
    "-s",
    "--savepath",
    help="Path to folder where game state will be saved (default: %(default)s)",
    type=Path,
    default="save",
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
logger = logging.getLogger(__name__)
logger.info(f"Configured logger at level {args.level}")

# Ensure the save-path exists and is a directory
logger.info(f"Checking savepath '{args.savepath}'")
try:
    if args.savepath.exists():
        if not args.savepath.is_dir():
            raise NotADirectoryError(args.savepath)
    else:
        args.savepath.mkdir()
except:
    logger.exception(f"Error opening or creating savepath '{args.savepath}'")
    raise SystemExit(1)

# Run server!
logger.info(f"Launching server loop for {args.address}:{args.port}")
with Server((args.address, args.port), args.savepath) as s:
    s.run()
