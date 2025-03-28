from threading import Lock
from pickle import dump, load
from random import Random, randrange

# A class for a single player
class Player:

    def __init__(self, name):
        self.__lock = Lock()

        # account name
        self.__name = name

        # save/resumable player info
        self.__data = {
            'PCSA': bytearray(),
            'PCIN': bytearray(),
            'PCOU': bytearray(),
            'PCQK': bytearray(),
            'slot': 0,
            'perm': [ 1, 1, 1, 1 ],
            'seed': [ 0, 0, 0, 0 ],
            'flag': [ 1, 0, 0, 0 ],
            'name': [ 'Larry', '', '', '' ],
            'position': [ 0, 0 ],
            'region': 0
        }

        try:
            self.load(name + ".pickle")
        except FileNotFoundError:
            print("Creating new character for " + name)

    #def __del__(self):
        #self.save(self.name)

    # getter / setter methods that use the lock
    def get_slot(self):
        with self.__lock:
            return self.__data['slot']

    def set_slot(self, slot):
        with self.__lock:
            self.__data['slot'] = slot

    def get_name(self, slot):
        with self.__lock:
            return self.__data['name'][slot]

    def set_name(self, slot, name):
        with self.__lock:
            self.__data['name'][slot] = name

    def get_seed(self, slot):
        with self.__lock:
            return self.__data['seed'][slot]

    def get_perm(self, slot):
        with self.__lock:
            return self.__data['perm'][slot]

    def get_flag(self, slot):
        with self.__lock:
            return self.__data['name'][slot] != ''

    def inc_seed(self, slot):
        with self.__lock:
            # personal RNG
            random = Random()
            random.seed(self.__data['seed'][slot])
            self.__data['seed'][slot] = random.randrange(0xFFFFFFFF)

            return self.__data['seed'][slot]

    def set_position(self, x, y, region):
        with self.__lock:
            self.__data['position'] = [x, y]
            self.__data['region'] = region

    def get_position(self):
        with self.__lock:
            return self.__data['position']

    def get_region(self):
        with self.__lock:
            return self.__data['region']

    def read(self, block, addr, length):
        with self.__lock:
            addrlen = addr + length
            shortage = addrlen - len(self.__data[block])
            if shortage > 0:
                # zero-fill to reach addr + len
                self.__data[block].extend(bytearray(shortage))

            print("Read from {} {}:{}".format(block, addr, addrlen))
            return self.__data[block][addr:addrlen]


    def write(self, block, addr, data):
        with self.__lock:
            addrlen = addr + len(data)
            shortage = addrlen - len(self.__data[block])
            if shortage > 0:
                # zero-fill to reach addr + len
                self.__data[block].extend(bytearray(shortage))

            print("Write to {} {}:{}".format(block, addr, addrlen))
            self.__data[block][addr:addrlen] = data

    def save(self, filename):
        with open(filename, 'wb') as f:
            dump(self.__data, f)

    def load(self, filename):
        with open(filename, 'rb') as f:
            self.__data = load(f)

# a class that holds all connected players
class Players:


    # Players class has locks on accessing anything
    #  And helper methods for searching by name, region, etc
    def __init__(self):
        self.__lock = Lock()

        self.__players = {}

    def __getitem__(self, arg):
        with self.__lock:
            return self.__players[arg]

    def add_player(self, name):
        with self.__lock:
            while True:
                # roll up a new perm_id for this session
                new_id = randrange(1, 0x7FFFFFFF)
                if new_id not in self.__players:
                    self.__players[new_id] = Player(name)
                    return new_id

    def drop_player(self, id):
        with self.__lock:
            try:
                del self.__players[id]
            except KeyError:
                print(f"Couldn't drop player {id} because they are already dropped")


    def id_by_name(self, name):
        with self.__lock:
            for id, player in self.__players.items():
                if player.__name == name:
                    return id

        return None

    def ids_in_region(self, region):
        ids = []
        with self.__lock:
            for id, player in self.__players.items():
                if player.get_region() == region:
                    ids.append(id)

        return ids
