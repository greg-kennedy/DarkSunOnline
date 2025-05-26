"""Sqlite3-powered database for DSOServer"""

import sqlite3
from logging import getLogger

logger = getLogger(__name__)


class Database:
    """
    Abstract class for persistent storage (save/load of world and player data)

    The Database class needs only support the methods below.
    State and Player classes serialize their state using these methods.
    """

    def get_login(self, username, password):
        """Return the ID matching a login on username + password"""
        return None

    def get_glob(self):
        """Return a dict of key => value read from the db"""
        return {}

    def get_regions(self):
        """Return a Set of all known region IDs"""
        return set()

    def get_glrg(self, region):
        """Return a dict of key => value for one region"""
        return {}

    def get_player(self, username):
        """Return a dict of key => value for the player of id"""
        return {}

    def save_glob(self, data):
        """Save a GLOB dict to the db"""
        pass

    def save_glrg(self, region, data):
        """Save one region to the GLRG section of db"""
        pass

    def save_player(self, username, data):
        """Save a player's data to the db"""
        pass


class Sqlite3(Database):
    """
    This is a sqlite3 database for DSOServer. It stores player and world state in a sqlite3 db.

    If you want to swap in something else (filesystem, mysql, etc) make sure you provide the same methods
    """

    __slots__ = "connection"

    def __init__(self, path):
        logger.info(f"Initializing database from {path}")
        # Open new sqlite connection to named database
        self.connection = sqlite3.connect(path, detect_types=sqlite3.PARSE_DECLTYPES)

        # initial state setup
        self.connection.execute("PRAGMA foreign_keys=1")

        # create tables if not exist
        self.connection.execute(
            "CREATE TABLE IF NOT EXISTS login(id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT NOT NULL COLLATE NOCASE, password TEXT NOT NULL, UNIQUE(username)) STRICT"
        )
        self.connection.execute(
            "CREATE TABLE IF NOT EXISTS glob(key INTEGER PRIMARY KEY, data BLOB NOT NULL) STRICT"
        )
        self.connection.execute(
            "CREATE TABLE IF NOT EXISTS glrg(region INTEGER NOT NULL, key INTEGER NOT NULL, data BLOB NOT NULL, PRIMARY KEY(region, key)) WITHOUT ROWID, STRICT"
        )
        self.connection.execute(
            "CREATE TABLE IF NOT EXISTS player(id INTEGER NOT NULL, key TEXT NOT NULL, data BLOB NOT NULL, PRIMARY KEY(id, key), FOREIGN KEY(id) REFERENCES login(id) ON DELETE CASCADE ON UPDATE CASCADE) WITHOUT ROWID, STRICT"
        )

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.connection.close()

    def get_login(self, username, password):
        result = self.connection.execute(
            "SELECT id FROM login WHERE username=? AND password=?",
            (username, password),
        ).fetchone()

        if result:
            return result[0]
        return None

    def get_glob(self):
        return {
            key: bytearray(data)
            for key, data in self.connection.execute(
                "SELECT key, data FROM glob ORDER BY key"
            ).fetchall()
        }

    def get_regions(self):
        return set(
            self.connection.execute(
                "SELECT DISTINCT region FROM glrg ORDER BY region"
            ).fetchall()
        )

    def get_glrg(self, region):
        return {
            key: bytearray(data)
            for key, data in self.connection.execute(
                "SELECT key, data FROM glrg WHERE region=? ORDER BY key", (region,)
            ).fetchall()
        }

    def get_player(self, id):
        return {
            key: bytearray(data)
            for key, data in self.connection.execute(
                "SELECT key, data FROM player WHERE id=? ORDER BY key",
                (id,),
            ).fetchall()
        }

    def save_glob(self, glob):
        with self.connection as conn:
            conn.executemany(
                "INSERT INTO glob VALUES(?, ?) ON CONFLICT(key) DO UPDATE SET data=excluded.data",
                glob.items(),
            )

    def save_glrg(self, region, glrg):
        with self.connection as conn:
            conn.executemany(
                "INSERT INTO glrg VALUES(?, ?, ?) ON CONFLICT(region, key) DO UPDATE SET data=excluded.data",
                [(region, key, data) for key, data in glrg.items()],
            )

    def save_player(self, id, player):
        with self.connection as conn:
            conn.executemany(
                "INSERT INTO player VALUES(?, ?, ?) ON CONFLICT(id, key) DO UPDATE SET data=excluded.data",
                [(id, key, data) for key, data in player.items()],
            )
