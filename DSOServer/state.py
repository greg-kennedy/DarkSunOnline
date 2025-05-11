from pickle import dump, load


class State:

    def __init__(self):
        self.__glob_data = {}

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
        try:
            block = self.__glob_data[data_type]
        except KeyError:
            block = bytearray(addr + length)
            self.__glob_data[data_type] = block

        return State.__read(block, addr, length)

    # Read from glReGional memory
    def read_glrg(self, region, data_type, addr, length):
        try:
            region_data = self.__glrg_region[region]
        except KeyError:
            region_data = {}
            self.__glrg_region[region] = region_data

        try:
            block = region_data[data_type]
        except KeyError:
            block = bytearray(addr + length)
            region_data[data_type] = block

        return State.__read(block, addr, length)

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
        try:
            block = self.__glob_data[data_type]
        except KeyError:
            block = bytearray(addr + len(data))
            self.__glob_data[data_type] = block

        # accept write and return
        State.__write(block, addr, data)

        return True

    def write_glrg(self, region, data_type, addr, data):
        try:
            region_data = self.__glrg_region[region]
        except KeyError:
            region_data = {}
            self.__glrg_region[region] = region_data

        try:
            block = region_data[data_type]
        except KeyError:
            block = bytearray(addr + len(data))
            region_data[data_type] = block

        # accept write and return
        State.__write(block, addr, data)

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
            self.__glob_data[key] = data

        for region, region_data in input['GLRG'].items():
            self.__glrg_region[region] = {}
            for key, data in region_data.items():
                self.__glrg_region[region][key] = data
