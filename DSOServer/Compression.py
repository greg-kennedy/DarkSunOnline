def RLECompress(data):
    result = bytearray()

    start = 0
    length = len(data)
    while start < length:
        end = start + 1

        if end < length and data[start] == 0 and data[end] == 0:
            # a run of zeroes, add as many as we can to the list and emit
            end += 1
            while end - start < 129 and end < length and data[end] == 0:
                end += 1
            result.append(0x101 - (end - start))
            start = end

        else:
            # advance until we run out of block, or off end of data
            while end - start < 128 and end < length:
                # check for 2x zeros and if so exit loop, we'll get it next time
                if end + 1 < length and data[end] == 0 and data[end + 1] == 0:
                    break
                else:
                    end += 1

            result.append(end - start - 1)
            while start < end:
                result.append(data[start])
                start += 1

    return result


def RLEUncompress(data):
    result = bytearray()

    ptr = 0
    length = len(data)
    while ptr < length:
        count = data[ptr]
        ptr += 1
        if count < 0x80:
            # copy the next (count + 1) bytes to output
            # TODO: use array slices to do this directly
            while count >= 0:
                result.append(data[ptr])
                count -= 1
                ptr += 1
        else:
            # Zero-stuff (0xFF - count + 2) bytes to output
            count = 0x101 - count
            # TODO: use list comprehension to add multiple elems at once
            while count:
                result.append(0)
                count -= 1

    return result


def EncodeString(string):
    return (len(string) + 1).to_bytes(4, "little") + bytes(string, "ascii") + bytes(1)


def DecodeString(data):
    length = int.from_bytes(data[0:4], byteorder="little")
    # check length: 4b msg_length, then message
    assert len(data) == 4 + length
    # check null-terminator
    assert data[4 + length - 1] == 0
    return str(data[4 : 4 + length - 1], "ascii")


def i32(i):
    return i.to_bytes(4, "little")
