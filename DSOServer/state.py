from threading import Lock
from pickle import dump, load

class State:

    def __init__(self, filename=None):
        # TODO: Would be nice if we could lock only certain segments, instead of the entire world
        self.lock = Lock()

        with self.lock:
            self.data = {}

        if filename:
            self.load(filename)

    def read(self, block, datatype, addr, length):
        with self.lock:
            if block not in self.data:
                self.data[block] = {}
            if datatype not in self.data[block]:
                self.data[block][datatype] = bytes()

            addrlen = addr + length
            shortage = addrlen - len(self.data[block][datatype])
            if shortage > 0:
                # zero-fill to reach addr + len
                #print("Requested len {} bytes from {}, endpoint {}, which is beyond {} by {}".format( length, addr, addrlen, len(self.data[block][datatype]), shortage))
                self.data[block][datatype] += bytes(shortage)
                #print("Extended to {}".format( len(self.data[block][datatype])))

            #print("READ {}, {} => {}", block, datatype, self.data[block][datatype])

            return self.data[block][datatype][addr:addrlen]



    def write(self, block, datatype, addr, data):
        with self.lock:
            if block not in self.data:
                self.data[block] = {}
            if datatype not in self.data[block]:
                self.data[block][datatype] = bytes()

            addrlen = addr + len(data)
            shortage = addrlen - len(self.data[block][datatype])
            if shortage > 0:
                # zero-fill to reach addr + len
                self.data[block][datatype] += bytes(shortage)

            self.data[block][datatype][addr:addrlen] = data


    def save(self, filename):
        with self.lock:
            with open(filename, 'wb') as f:
                dump(self.data, f)

    def load(self, filename):
        with self.lock:
            with open(filename, 'rb') as f:
                self.data = load(f)
