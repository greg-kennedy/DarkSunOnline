import socket
import logging
from os import getpid
from time import time
from datetime import datetime
from socketserver import ThreadingTCPServer, BaseRequestHandler

from .compression import RLECompress, RLEUncompress
from .state import State
from .player import Players

# listen on any interface, port 14902
HOST = ''
PORT = 14902

logging.basicConfig(level=logging.NOTSET)
logger = logging.getLogger(__name__)

state = State()
players = Players()


def to_printable_ascii(byte):
    return chr(byte) if 32 <= byte <= 126 else "."


def hexdump(data: bytes):
    offset = 0
    while offset < len(data):
        chunk = data[offset : offset + 16]
        hex_values = " ".join(f"{byte:02x}" for byte in chunk)
        ascii_values = "".join(to_printable_ascii(byte) for byte in chunk)
        print(f"{offset:08x}  {hex_values:<48}  |{ascii_values}|")
        offset += 16


# TODO this probably isn't thread-safe since it gets a bunch of info
def buildSlotResults(perm_id):
    # 'dsIN', 4 bytes myPermId, 4x1 byte slot permission levels
    # perm. id >= 0x80000000 gives "No host response"
    player = players[perm_id]

    response = bytes('dsIN', 'ascii') + perm_id.to_bytes(4, 'little')
    for i in range(4):
        response += bytes( [player.get_perm(i)] )

    # currently selected name
    response += encodeString(player.get_name(player.get_slot()))

    # all 4 player names w/ flag
    for i in range(4):
        response += player.get_flag(i).to_bytes(4, 'little') + encodeString(player.get_name(i))

    # "Process ID"
    response += getpid().to_bytes(4, 'little')

    #self.logger.debug("Sending TEN Init response")
    #hexdump(response)
    return response


def encodeString(string):
    return (len(string) + 1).to_bytes(4, 'little') + bytes(string, 'ascii') + bytes(1)


def decodeString(data):
    length = int.from_bytes(data[0:4], byteorder='little')
    # check length: 4b msg_length, then message
    assert len(data) == 4 + length
    # check null-terminator
    assert data[-1] == 0
    return str(data[4:-1], 'ascii')


class ThreadedTCPRequestHandler(BaseRequestHandler):
    # helper to send a packet to the connected client
    #  it tries RLE compression for size reduction, and prepends the length as well
    def sendPacket(self, data):
        compressed = RLECompress(data)
        if len(compressed) < len(data):
            pkt = ((2 + len(compressed)) | 0x8000).to_bytes(2, 'little') + compressed
        else:
            pkt = (2 + len(data)).to_bytes(2, 'little') + data

        #self.logger.debug("Sending %scompressed packet", "" if pkt[1] & 0x80 else "UN")
        #hexdump(pkt)
        self.request.sendall(pkt)


    def setup(self):
        self.logger = logger.getChild("{}:{}".format(*self.client_address))
        self.player = None

    # a packet!
    def handle(self):

        while 1:
            # get 2 bytes of length
            pkt_length = int.from_bytes(self.request.recv(2, socket.MSG_WAITALL), byteorder='little')
            if not pkt_length:
                # client disconnect
                break

            # top bit of length indicates compression
            compressed, pkt_length = pkt_length & 0x8000, pkt_length & 0x7FFF

            # read and uncompress remaining bytes
            payload = self.request.recv(pkt_length - 2, socket.MSG_WAITALL)
            if not payload:
                # client disconnect
                break

            if compressed:
                payload = RLEUncompress(payload)

            # check tag (first 4 bytes) of payload
            id, payload = str(payload[0:4], 'ascii'), payload[4:]

            #self.logger.debug("Packet received (len=%d, id=%s, payload=%s)", length, id, payload)
            if id == 'DSIT':
                # TEN Init
                token = decodeString(payload)
                self.logger.debug("Received TEN Init packet (token=%s)", token)

                # if you close the socket after receiving this packet without responding,
                #  the remote reports this as "Account still logged on".

                # TODO: load player object from disk
                #  for now we create a dummy one
                self.player = players.add_player('Player')

                # If the user is already logged in, respond 'dsNI' instead
                #response = bytes('dsNI', 'ascii')

                self.sendPacket(buildSlotResults(self.player))


            elif id == 'DSLG':
                # client uploading logs to us
                #  the format is: 4 bytes string length, null-terminated ASCII string
                msg = decodeString(payload)
                self.logger.debug("Received client log: %s", msg)

                # no response to this

            elif id == 'DSSL':
                assert len(payload) == 0
                self.logger.info("Received client ping")

                response = bytes('dsSL', 'ascii') + int(time()).to_bytes(4, 'little')
                self.sendPacket(response)


            elif id == 'DSNS':
                # Client name selection - they want to change the current Slot
                assert len(payload) == 4
                slot_id = int.from_bytes(payload[0:4], byteorder='little')
                self.logger.info("Received New Slot Choice: %d", slot_id)

                players[self.player].set_slot(slot_id)

                # give back the player info struct again
                self.sendPacket(buildSlotResults(self.player))

            elif id == 'DSPS':
                # Client "set position"
                assert len(payload) == 20
                perm_id = int.from_bytes(payload[0:4], byteorder='little')
                unknown = int.from_bytes(payload[4:8], byteorder='little')
                x = int.from_bytes(payload[8:12], byteorder='little')
                y = int.from_bytes(payload[12:16], byteorder='little')
                reg = int.from_bytes(payload[16:20], byteorder='little')
                self.logger.info("Received Set Position for %d (type %d): (x=%d, y=%d, reg=%d)", perm_id, unknown, x, y, reg)

                players[self.player].set_position(x, y, reg)

                # the "response" is a collected list of positions, where "1" is the count and then the payloads are from each other packet
                response = bytes('dsPS', 'ascii') + perm_id.to_bytes(4, 'little') + (1).to_bytes(4, 'little') + perm_id.to_bytes(4, 'little') + unknown.to_bytes(4, 'little') + x.to_bytes(4, 'little') + y.to_bytes(4, 'little') + reg.to_bytes(4, 'little')
                self.sendPacket(response)


            elif id == 'DSDT':
                # Client requesting Host Date
                assert len(payload) == 4
                perm_id = int.from_bytes(payload[0:4], byteorder='little')
                self.logger.info("Received Host Date req from %d", perm_id)

                # calculate days and seconds since Jan. 1 of this year
                #  TODO: this may be incorrect, it might be days since epoch, or seconds since, etc
                now = datetime.now()
                epoch = now.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
                diff = now - epoch

                response = bytes('dsDT', 'ascii') + diff.seconds.to_bytes(4, 'little') + diff.days.to_bytes(4, 'little')
                self.sendPacket(response)


            elif id == 'DSRS':
                # Client making a "Read Seed" request
                assert len(payload) == 8
                perm_id = int.from_bytes(payload[0:4], byteorder='little')
                slot_id = int.from_bytes(payload[4:8], byteorder='little')
                self.logger.info("Received 'Read Seed' (%d) request from %d", slot_id, perm_id)

                response = bytes('dsRS', 'ascii') + perm_id.to_bytes(4, 'little') + slot_id.to_bytes(4, 'little') + players[self.player].get_seed(slot_id).to_bytes(4, 'little')
                self.sendPacket(response)

            elif id == 'DSRL':
                # Client making a "Roll Dice" request
                assert len(payload) == 8
                perm_id = int.from_bytes(payload[0:4], byteorder='little')
                slot_id = int.from_bytes(payload[4:8], byteorder='little')
                self.logger.info("Received 'Roll Dice' request from %d:%d", perm_id, slot_id)

                response = bytes('dsRL', 'ascii') + perm_id.to_bytes(4, 'little') + slot_id.to_bytes(4, 'little') + players[self.player].inc_seed(slot_id).to_bytes(4, 'little')
                self.sendPacket(response)

            elif id == 'DSNM':
                # Client checking if desired name is OK.
                slot_id = int.from_bytes(payload[0:4], byteorder='little')
                name = decodeString(payload[4:])
                self.logger.info("Received 'Name OK?' request, slot=%d name=%s", slot_id, name)

                # TODO: We always approve names now, but it would be good to know
                #  which packet indicates "name no good" (dsNO?  dsNR?)
                players[self.player].set_name(slot_id, name)

                # the client also complains if you ack a 0-byte name, so we should not do that either
                response = bytes('dsNM', 'ascii') + slot_id.to_bytes(4, 'little') + encodeString(name)
                self.sendPacket(response)

            elif id == 'DSRI':
                # "Region Info" request - player wants to know who is in the region with them
                assert len(payload) == 8
                perm_id = int.from_bytes(payload[0:4], byteorder='little')
                region_id = int.from_bytes(payload[4:8], byteorder='little')
                self.logger.info("Received Region Info request, perm_id=%d rgn=%d", perm_id, region_id)

                ids = players.ids_in_region(region_id)
                self.logger.info(" There are " + str(len(ids)) + " players in region: " + str(ids))

                response = bytes('dsRI', 'ascii') + perm_id.to_bytes(4, 'little') + region_id.to_bytes(4, 'little') + (-len(ids)).to_bytes(4, 'little', signed=True)
                for i in ids:
                    response += i.to_bytes(4, 'little')

                self.sendPacket(response)

            elif id == 'DSRD':
                # Client making a Read Request of something
                #  There are different types of things to Read:
                #  PCSA (save), GLRG (region?), GLOB (global?), PCIN / PCOU, and PCQK
                # but they all start with an ID...
                assert len(payload) == 24
                perm_id = int.from_bytes(payload[0:4], byteorder='little')
                rd_block = str(payload[4:8], 'ascii')
                rd_index1 = int.from_bytes(payload[8:12], byteorder='little')
                rd_index2 = int.from_bytes(payload[12:16], byteorder='little')
                #  address and length of data block to read
                rd_addr = int.from_bytes(payload[16:20], byteorder='little')
                rd_len = int.from_bytes(payload[20:24], 'little')

                self.logger.info("Received 'Read' (block=%s) request from %d: (index1=%d, index2=%d, addr=%d, len=%d)", rd_block, perm_id, rd_index1, rd_index2, rd_addr, rd_len)
                if rd_block == 'GLOB':
                    # read of "global" shared memory area - things like high score tables, etc
                    #  each type is numbered differently, there are 0x16 of them
                    assert rd_index2 == 0

                    # send bytes back by getting them from the global state holder
                    block = state.read_glob(rd_index1, rd_addr, rd_len)

                elif rd_block == 'GLRG':
                    # read of "region" shared memory area - things like objects, items, etc
                    # data type, 0-5 or so (actually client usually requests 6?  weird)
                    block = state.read_glrg(rd_index1, rd_index2, rd_addr, rd_len)

                elif rd_block == 'PCSA':
                    # Player save file info.  These don't have multiple subsections.  Also you should only read your own data.
                    assert rd_index1 == 0
                    assert rd_index2 == 0
                    #  address and length of data block to read
                    key = 1
                    block = players[self.player].read('PCSA', rd_addr, rd_len)

                elif rd_block == 'PCIN' or rd_block == 'PCOU' or rd_block == 'PCQK':
                    # read of "global" shared memory area - things like high score tables, etc
                    #  each type is numbered differently, there are 0x16 of them
                    # Stub these in for now with all-0
                    assert rd_index2 == 0
                    key = 1
                    block = players[rd_index1].read(rd_block, rd_addr, rd_len)

                else:
                    assert False

                response = bytes('dsRD', 'ascii') + perm_id.to_bytes(4, 'little') + bytes(rd_block, 'ascii')+ rd_index1.to_bytes(4, 'little') + rd_index2.to_bytes(4, 'little') + key.to_bytes(4, 'little') + rd_addr.to_bytes(4, 'little') + rd_len.to_bytes(4, 'little') + block
                self.sendPacket(response)

            elif id == 'DSWQ':
                # Client making a Write Request of some shared memory segment, GLOB or GLRG.
                #  Since this could be contentious, it expects back a dsWT (write OK)
                #  or a dsWE (write Error)
                # The client calls this a "useBroadcast" write
                perm_id = int.from_bytes(payload[0:4], byteorder='little')
                wt_block = str(payload[4:8], 'ascii')
                wt_index1 = int.from_bytes(payload[8:12], byteorder='little')
                wt_index2 = int.from_bytes(payload[12:16], byteorder='little')
                # key SHOULD likely be used to resolve race conditions, but it's always 0 in 1.0
                wt_key = int.from_bytes(payload[16:20], byteorder='little')
                assert wt_key == 0
                #  address and length of data block to write
                wt_addr = int.from_bytes(payload[20:24], byteorder='little')
                wt_len = int.from_bytes(payload[24:28], 'little')
                assert wt_len == len(payload[28:])
                self.logger.info("Received 'Write Broadcast' (block=%s) request from %d: (index1=%d, index2=%d, key=%d, addr=%d, len=%d)", wt_block, perm_id, wt_index1, wt_index2, wt_key, wt_addr, wt_len)

                if wt_block == 'GLOB':
                    # write of "global" shared memory area - should never have an index2 set
                    assert wt_index2 == 0
                    success = state.write_glob(wt_index1, wt_addr, payload[28:])
                elif wt_block == 'GLRG':
                    # write of "region" shared memory area
                    success = state.write_glrg(wt_index1, wt_index2, wt_addr, payload[28:])
                else:
                    assert False

                # ack or nack this
                if success:
                    response = bytes('dsWT', 'ascii')
                else:
                    response = bytes('dsWE', 'ascii')

                key = 1
                response += perm_id.to_bytes(4, 'little') + bytes(wt_block, 'ascii') + wt_index1.to_bytes(4, 'little') + wt_index2.to_bytes(4, 'little') + key.to_bytes(4, 'little') + wt_len.to_bytes(4, 'little')
                self.sendPacket(response)


            elif id == 'DSWT':
                # Client making a Write Request of something
                #  There are different types of things to Write:
                #  PCSA (save), PCQK, PCIN and PCOU
                perm_id = int.from_bytes(payload[0:4], byteorder='little')
                wt_block = str(payload[4:8], 'ascii')
                wt_index1 = int.from_bytes(payload[8:12], byteorder='little')
                wt_index2 = int.from_bytes(payload[12:16], byteorder='little')
                # key SHOULD likely be used to resolve race conditions, but it's always 0 in 1.0
                wt_key = int.from_bytes(payload[16:20], byteorder='little')
                assert wt_key == 0
                #  address and length of data block to write
                wt_addr = int.from_bytes(payload[20:24], byteorder='little')
                wt_len = int.from_bytes(payload[24:28], 'little')
                assert wt_len == len(payload[28:])

                self.logger.info("Received 'Write Player Char' (block=%s) request from %d: (index1=%d, index2=%d, key=%d, addr=%d, len=%d)", wt_block, perm_id, wt_index1, wt_index2, wt_key, wt_addr, wt_len)

                if wt_block == 'PCSA':
                    # trying to save character - everything is ignored except the address and payload
                    assert wt_index1 == 0
                    assert wt_index2 == 0
                    players[self.player].write('PCSA', wt_addr, payload[28:])

                elif wt_block == 'PCIN' or wt_block == 'PCOU' or wt_block == 'PCQK':
                    # trying to write to someone's 'outbox'
                    if (wt_index1 == 0):
                        wt_index1 = self.player
                    assert wt_index2 == 0
                    players[wt_index1].write(wt_block, wt_addr, payload[28:])

                else:
                    hexdump(payload)


            else:
                self.logger.debug("Packet received (len=%d, id=%s, payload=%s)", len(payload), id, payload)
                hexdump(payload)
                self.logger.debug("Ignoring packet")

    def finish(self):
        # try dsCL see if we can get them to drop
        if self.player:
            players[self.player].save('player.pickle')
            response = bytes('dsCL', 'ascii') + self.player.to_bytes(4, 'little')
            self.sendPacket(response)


def run(argv):
    ThreadingTCPServer.allow_reuse_address = True
    server = ThreadingTCPServer((HOST, PORT), ThreadedTCPRequestHandler)
    try:
        state.load('world.pickle')
    except FileNotFoundError:
        logger.info("Did not find existing world to resume")

    with server:
        # run until ctrl+C pressed
        server.serve_forever()
    state.save('world.pickle')
