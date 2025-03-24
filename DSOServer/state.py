from threading import Lock
from pickle import dump, load

class State:

    def __init__(self, filename=None):
        # TODO: Would be nice if we could lock only certain segments, instead of the entire world
        self.lock = Lock()

        with self.lock:
            self.data = {'GLOB': {}, 'GLRG': {}}
            #self.keys = {'GLOB': {}, 'GLRG': {}}

        if filename:
            self.load(filename)

    # static method to read from a list and return, adding empty bytes as needed
    def read(block, addr, length):
        addrlen = addr + length
        shortage = addrlen - len(block)
        if shortage > 0:
            # zero-fill to reach addr + len
            block += bytes(shortage)

        return block[addr:addrlen]

    def read_glob(self, data_type, addr, length):
        with self.lock:
            if data_type not in self.data['GLOB']:
                self.data['GLOB'][data_type] = bytes()
                #self.keys['GLOB'][data_type] = 1

            #return (self.keys['GLOB'][data_type], State.read(self.data['GLOB'][data_type], addr, length))
            return (1, State.read(self.data['GLOB'][data_type], addr, length))

    def read_glrg(self, region, data_type, addr, length):
        with self.lock:
            if region not in self.data['GLRG']:
                self.data['GLRG'][region] = {}
                #self.keys['GLRG'][region] = {}
            if data_type not in self.data['GLRG'][region]:
                self.data['GLRG'][region][data_type] = bytes()
                #self.keys['GLRG'][region][data_type] = 1

            #return (self.keys['GLRG'][region][data_type], State.read(self.data['GLRG'][region][data_type], addr, length))
            return (1, State.read(self.data['GLRG'][region][data_type], addr, length))

    #### WRITE to global memory
    def write(block, addr, data):
        addrlen = addr + len(data)
        shortage = addrlen - len(block)
        if shortage > 0:
            # zero-fill to reach addr + len
            block += bytes(shortage)

        block = block[:addr] + data + block[addrlen:]

    def write_glob(self, key, data_type, addr, data):
        with self.lock:
            if data_type not in self.data['GLOB']:
                self.data['GLOB'][data_type] = bytes()
                #self.keys['GLOB'][data_type] = 1

            # reject write if incoming key does not match expected key
            #if key != self.keys['GLOB'][data_type]:
                #return (self.keys['GLOB'][data_type], False)

            # accept write, increment key, and return
            State.write(self.data['GLOB'][data_type], addr, data)
            #self.keys['GLOB'][data_type] += 1
            #return (self.keys['GLOB'][data_type], True)
            return (1, True)

    def write_glrg(self, key, region, data_type, addr, length):
        with self.lock:
            if region not in self.data['GLRG']:
                self.data['GLRG'][region] = {}
                #self.keys['GLRG'][region] = {}
            if data_type not in self.data['GLRG'][region]:
                self.data['GLRG'][region][data_type] = bytes()
                #self.keys['GLRG'][region][data_type] = 1

            # reject write if incoming key does not match expected key
            #  This doesn't seem to actually occur, so comment it out
            #if key != self.keys['GLRG'][region][data_type]:
                #return (self.keys['GLRG'][region][data_type], False)

            # accept write, increment key, and return
            State.write(self.data['GLRG'][region][data_type], addr, data)
            #self.keys['GLRG'][region][data_type] += 1
            #return (self.keys['GLRG'][region][data_type], True)
            return (1, True)

    # pickle and unpickle state
    def save(self, filename):
        with self.lock:
            with open(filename, 'wb') as f:
                dump(self.data, f)

    def load(self, filename):
        with self.lock:
            with open(filename, 'rb') as f:
                self.data = load(f)
