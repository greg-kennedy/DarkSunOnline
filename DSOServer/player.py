from threading import Lock
from pickle import dump, load
from random import Random

class Player:

    def __init__(self, id, filename=None):
        # session ID
        self.id = id

        # TODO: Would be nice if we could lock only certain segments, instead of the entire player
        self.lock = Lock()

        with self.lock:
            # save/resumable player info
            self.data = {
                'PCSA': bytes(),
                'slot': 0,
                'perm': [ 0, 0, 0, 0 ],
                'seed': [ 0, 0, 0, 0 ],
                'flag': [ 1, 0, 0, 0 ],
                'name': [ 'Larry', '', '', '' ]
            }

        if filename:
            try:
                self.load(filename)
            except FileNotFoundError:
                pass

    def get_slot(self):
        with self.lock:
            return self.data['slot']

    def set_slot(self, slot):
        with self.lock:
            self.data['slot'] = slot

    def get_name(self, slot):
        with self.lock:
            return self.data['name'][slot]

    def set_name(self, slot, name):
        with self.lock:
            self.data['name'][slot] = name

    def get_seed(self, slot):
        with self.lock:
            return self.data['seed'][slot]

    def get_perm(self, slot):
        with self.lock:
            return self.data['perm'][slot]

    def get_flag(self, slot):
        with self.lock:
            return self.data['name'][slot] != ''

    def inc_seed(self, slot):
        with self.lock:
            # personal RNG
            random = Random()
            random.seed(self.data['seed'][slot])
            self.data['seed'][slot] = random.randrange(0xFFFFFFFF)

            return self.data['seed'][slot]

    def read(self, addr, length):
        with self.lock:
            addrlen = addr + length
            shortage = addrlen - len(self.data['PCSA'])
            if shortage > 0:
                # zero-fill to reach addr + len
                self.data['PCSA'] += bytes(shortage)

            return self.data['PCSA'][addr:addrlen]



    def write(self, addr, data):
        with self.lock:
            addrlen = addr + len(data)
            shortage = addrlen - len(self.data['PCSA'])
            if shortage > 0:
                # zero-fill to reach addr + len
                self.data['PCSA'] += bytes(shortage)

            self.data['PCSA'] = self.data['PCSA'][:addr] + data + self.data['PCSA'][addrlen:]

    def save(self, filename):
        with self.lock:
            with open(filename, 'wb') as f:
                dump(self.data, f)

    def load(self, filename):
        with self.lock:
            with open(filename, 'rb') as f:
                self.data = load(f)
