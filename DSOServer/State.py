"""Class for managing world-state"""

from logging import getLogger

logger = getLogger(__name__)

from time import time
from random import Random, randrange, randbytes


# A class for a single player
class Player:

    #__slots__ = "database", "name", "data"

    def __init__(self, database, name):
        # shared db
        self.database = database

        # account name
        self.name = name

        # save/resumable player info
        self.data = database.get_player(name)

        self.data_slot = {
            "slot": 0,
            "perm": [1, 1, 1, 1],
            "seed": [0, 0, 0, 0],
            "flag": [0, 0, 0, 0],
            "name": ["", "", "", ""],
            "position": [0, 0],
            "region": 0,
        }

    def inc_seed(self, slot):
        # personal RNG
        random = Random()
        random.seed(self.data_slot["seed"][slot])
        self.data_slot["seed"][slot] = random.randrange(0xFFFFFFFF)

        return self.data_slot["seed"][slot]

    def set_position(self, x, y, region):
        self.data_slot["position"] = [x, y]
        self.data_slot["region"] = region

    def read(self, data_type, addr, length):
        """Read from GLOBal memory"""
        try:
            data = self.data[data_type][addr : addr + length]
            return data + bytes(length - len(data))
        except KeyError:
            return bytes(length)

    def write(self, data_type, addr, data):
        """Write to global memory"""
        try:
            self.data[data_type][addr : addr + len(data)] = data
        except KeyError:
            self.data[data_type] = bytearray(addr) + data

    def close(self):
        self.database.save_player(self.name, self.data)


class State:
    """A class that manages all World State.  Also contains functions to load or save Players in the world"""

    __slots__ = "glob", "glrg", "players", "tokens", "database"

    def __init__(self, database):
        self.database = database

        self.glob = database.get_glob()
        self.glrg = {}
        for region in database.get_regions():
            self.glrg[region] = database.get_glrg(region)

        # connected players
        self.players = {}

        # login tokens
        self.tokens = {}

    def close(self):
        self.tokens = {}

        for player in self.players.values():
            player.close()

        self.players = {}

        for region, data in self.glrg.items():
            self.database.save_glrg(region, data)
        self.glrg = {}
        self.database.save_glob(self.glob)
        self.glob = {}

    # #########################################################################
    def read_glob(self, data_type, addr, length):
        """Read from GLOBal memory"""
        try:
            data = self.glob[data_type][addr : addr + length]
            return data + bytes(length - len(data))
        except KeyError:
            return bytes(length)

    def read_glrg(self, region, data_type, addr, length):
        """Read from glReGional memory"""
        try:
            data = self.glrg[region][data_type][addr : addr + length]
            return data + bytes(length - len(data))
        except KeyError:
            return bytes(length)

    # #########################################################################
    def write_glob(self, data_type, addr, data):
        """Write to global memory"""
        try:
            self.glob[data_type][addr : addr + len(data)] = data
        except KeyError:
            self.glob[data_type] = bytearray(addr) + data

    def write_glrg(self, region, data_type, addr, data):
        """Write to glReGional memory"""
        try:
            region_data = self.glrg[region]
        except KeyError:
            region_data = {}
            self.glrg[region] = region_data

        try:
            region_data[data_type][addr : addr + len(data)] = data
        except KeyError:
            region_data[data_type] = bytearray(addr) + data

    # #########################################################################
    def _expire_tokens(self):
        # remove any "expired" logins from the table
        #  that is anything > 60 seconds old
        expiration = time() - 60

        for token, (username, timestamp) in self.tokens.items():
            if timestamp < expiration:
                del self.tokens[token]

    def get_login_token(self, username, password):
        """Checks a username + password and returns a login token or None"""

        self._expire_tokens()

        if self.database.get_login(username, password):
            token = randbytes(7).hex()
            self.tokens[token] = (username, time())
            return token
            
        else:
            return None

    def return_login_token(self, token):
        """Returns the username for a supplied login token"""

        self._expire_tokens()

        # now try to retrieve the username
        detail = self.tokens.get(token)
        if detail:
            return detail[0]

        return None

    # #########################################################################
    def add_player(self, name):
        while True:
            # roll up a new perm_id for this session
            new_id = randrange(1, 0x7FFFFFFF)
            if new_id not in self.players:
                self.players[new_id] = Player(self.database, name)
                return new_id

    def drop_player(self, id):
        try:
            self.players[id].close()
            del self.players[id]
        except KeyError:
            print(f"Couldn't drop player {id} because they are already dropped")

    def id_by_name(self, name):
        for id, player in self.players.items():
            if player.name == name:
                return id

        return None

    def ids_in_region(self, region):
        ids = []
        for id, player in self.players.items():
            if player.data_slot['region'] == region:
                ids.append(id)

        return ids
