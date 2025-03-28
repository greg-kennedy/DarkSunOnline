from threading import Lock
from pickle import dump, load


class State:

    def __init__(self):
        self.__glob_lock = Lock()
        self.__glob_data = {}

        self.__glrg_lock = Lock()
        self.__glrg_region = {}

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
        # acquire GLOB lock to get reference to the subitem
        with self.__glob_lock:
            try:
                block = self.__glob_data[data_type]
            except KeyError:
                block = {'lock': Lock(), 'data': bytearray(addr + length)}
                self.__glob_data[data_type] = block

        with block['lock']:
            return State.__read(block['data'], addr, length)

    # Read from glReGional memory
    def read_glrg(self, region, data_type, addr, length):
        # acquire GLRG lock to get reference to the region
        with self.__glrg_lock:
            try:
                region_data = self.__glrg_region[region]
            except KeyError:
                region_data = {'lock': Lock(), 'data': {}}
                self.__glrg_region[region] = region_data

        with region_data['lock']:
            try:
                block = region_data['data'][data_type]
            except KeyError:
                block = {'lock': Lock(), 'data': bytearray(addr + length)}
                region_data['data'][data_type] = block

        with block['lock']:
            return State.__read(block['data'], addr, length)

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
        with self.__glob_lock:
            try:
                block = self.__glob_data[data_type]
            except KeyError:
                block = {'lock': Lock(), 'data': bytearray(addr + len(data))}
                self.__glob_data[data_type] = block

        with block['lock']:
            # accept write and return
            State.__write(block['data'], addr, data)

        return True

    def write_glrg(self, region, data_type, addr, data):
        with self.__glrg_lock:
            try:
                region_data = self.__glrg_region[region]
            except KeyError:
                region_data = {'lock': Lock(), 'data': {}}
                self.__glrg_region[region] = region_data

        with region_data['lock']:
            try:
                block = region_data['data'][data_type]
            except KeyError:
                block = {'lock': Lock(), 'data': bytearray(addr + len(data))}
                region_data['data'][data_type] = block

        with block['lock']:
            # accept write and return
            State.__write(block['data'], addr, data)

        return True

    # #########################################################################
    # pickle and unpickle state
    def save(self, filename):
        output = {'GLOB': {}, 'GLRG': {}}
        for key, data in self.__glob_data.items():
            output['GLOB'][key] = data['data']

        for region, region_data in self.__glrg_region.items():
            output['GLRG'][region] = {}
            for key, data in region_data['data'].items():
                output['GLRG'][region][key] = data['data']

        with open(filename, 'wb') as f:
            dump(output, f)

    def load(self, filename):
        with open(filename, 'rb') as f:
            input = load(f)

        for key, data in input['GLOB'].items():
            self.__glob_data[key] = {'lock': Lock(), 'data': data}

        for region, region_data in input['GLRG'].items():
            self.__glrg_region[region] = {'lock': Lock(), 'data': {}}
            for key, data in region_data['data'].items():
                self.__glrg_region[region]['data'][key] = {'lock': Lock(), 'data': data}
