from pickle import dump, load
from random import Random, randrange

# A class for a single player
class Player:

    def __init__(self, name):
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
        return self.__data['slot']

    def set_slot(self, slot):
        self.__data['slot'] = slot

    def get_name(self, slot):
        return self.__data['name'][slot]

    def set_name(self, slot, name):
        self.__data['name'][slot] = name

    def get_seed(self, slot):
        return self.__data['seed'][slot]

    def get_perm(self, slot):
        return self.__data['perm'][slot]

    def get_flag(self, slot):
        return self.__data['name'][slot] != ''

    def inc_seed(self, slot):
        # personal RNG
        random = Random()
        random.seed(self.__data['seed'][slot])
        self.__data['seed'][slot] = random.randrange(0xFFFFFFFF)

        return self.__data['seed'][slot]

    def set_position(self, x, y, region):
        self.__data['position'] = [x, y]
        self.__data['region'] = region

    def get_position(self):
        return self.__data['position']

    def get_region(self):
        return self.__data['region']

    def read(self, block, addr, length):
        addrlen = addr + length
        shortage = addrlen - len(self.__data[block])
        if shortage > 0:
            # zero-fill to reach addr + len
            self.__data[block].extend(bytearray(shortage))

        print("Read from {} {}:{}".format(block, addr, addrlen))
        return self.__data[block][addr:addrlen]


    def write(self, block, addr, data):
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

