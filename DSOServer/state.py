from threading import Lock
from pickle import dump, load


class State:

    def __init__(self):
        # TODO: Would be nice if we could lock only certain segments, instead of the entire world
        self.__lock = Lock()
        self.__data = {'GLOB': {}, 'GLRG': {}}

    # #########################################################################
    # static method to read from a list and return, adding empty bytes as needed
    def __read(block, addr, length):
        addrlen = addr + length
        shortage = addrlen - len(block)
        if shortage > 0:
            # zero-fill to reach addr + len
            block.extend(bytearray(shortage))

        return bytes(block[addr:addrlen])

    # Read from GLOBal memory
    def read_glob(self, data_type, addr, length):
        with self.__lock:
            if data_type not in self.__data['GLOB']:
                self.__data['GLOB'][data_type] = bytearray()

            return State.__read(self.__data['GLOB'][data_type], addr, length)

    # Read from glReGional memory
    def read_glrg(self, region, data_type, addr, length):
        with self.__lock:
            if region not in self.__data['GLRG']:
                self.__data['GLRG'][region] = {}
            if data_type not in self.__data['GLRG'][region]:
                self.__data['GLRG'][region][data_type] = bytearray()

            return State.__read(self.__data['GLRG'][region][data_type], addr, length)

    # #########################################################################
    # WRITE to global memory
    def __write(block, addr, data):
        addrlen = addr + len(data)
        shortage = addrlen - len(block)
        if shortage > 0:
            # zero-fill to reach addr + len
            block.extend(bytearray(shortage))

        block[addr:addrlen] = data

    def write_glob(self, data_type, addr, data):
        with self.__lock:
            if data_type not in self.__data['GLOB']:
                self.__data['GLOB'][data_type] = bytearray()

            # accept write and return
            State.__write(self.__data['GLOB'][data_type], addr, data)

            return True

    def write_glrg(self, region, data_type, addr, data):
        with self.__lock:
            if region not in self.__data['GLRG']:
                self.__data['GLRG'][region] = {}
            if data_type not in self.__data['GLRG'][region]:
                self.__data['GLRG'][region][data_type] = bytearray()

            # accept write and return
            State.__write(self.__data['GLRG'][region][data_type], addr, data)
            return True

    # #########################################################################
    # pickle and unpickle state
    def save(self, filename):
        with self.__lock:
            with open(filename, 'wb') as f:
                dump(self.__data, f)

    def load(self, filename):
        with self.__lock:
            with open(filename, 'rb') as f:
                self.__data = load(f)
