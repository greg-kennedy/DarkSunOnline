import socket
import struct
import logging
from os import getpid
from time import time
from datetime import datetime
from socketserver import ThreadingTCPServer, BaseRequestHandler

from .compression import RLECompress, RLEUncompress
from .state import State
from .player import Player

# listen on any interface, port 14902
HOST = ''
PORT = 14902

logging.basicConfig(level=logging.NOTSET)
logger = logging.getLogger(__name__)

state = State()

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
                self.player = Player(0x0BADCAFE, 'player.pickle')

                # If the user is already logged in, respond 'dsNI' instead
                #response = bytes('dsNI', 'ascii')

                # 'dsIN', 4 bytes myPermId, 4x1 byte slot permission levels
                # perm. id >= 0x80000000 gives "No host response"
                response = bytes('dsIN', 'ascii') + self.player.id.to_bytes(4, 'little')
                for i in range(4):
                    response += bytes( [self.player.get_perm(i)] )

                # currently selected name
                response += encodeString(self.player.get_name(self.player.get_slot()))

                # all 4 player names w/ flag
                for i in range(4):
                    response += self.player.get_flag(i).to_bytes(4, 'little') + encodeString(self.player.get_name(i))

                # "Process ID"
                response += getpid().to_bytes(4, 'little')

                self.logger.debug("Sending TEN Init response")
                hexdump(response)
                self.sendPacket(response)

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
                self.logger.info("Received Name Selection: %d", slot_id)

                self.player.set_slot(slot_id)

                # give back the player info struct again

                response = bytes('dsIN', 'ascii') + self.player.id.to_bytes(4, 'little')
                for i in range(4):
                    response += bytes( [self.player.get_perm(i)] )

                response += encodeString(self.player.get_name(self.player.get_slot()))
                # 4 player names w/ flag
                for i in range(4):
                    response += self.player.get_flag(i).to_bytes(4, 'little') + encodeString(self.player.get_name(i))

                # "Process ID"
                response += getpid().to_bytes(4, 'little')

                self.logger.debug("Sending dsIN response to that")
                self.sendPacket(response)

            elif id == 'DSPS':
                # Client "set position"
                assert len(payload) == 20
                perm_id = int.from_bytes(payload[0:4], byteorder='little')
                unknown = int.from_bytes(payload[4:8], byteorder='little')
                x = int.from_bytes(payload[8:12], byteorder='little')
                y = int.from_bytes(payload[12:16], byteorder='little')
                reg = int.from_bytes(payload[16:20], byteorder='little')
                self.logger.info("Received Set Position for %d (type %d): (x=%d, y=%d, reg=%d)", perm_id, unknown, x, y, reg)

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
                seed_id = int.from_bytes(payload[4:8], byteorder='little')
                self.logger.info("Received 'Read Seed' (%d) request from %d", seed_id, perm_id)

                response = bytes('dsRS', 'ascii') + perm_id.to_bytes(4, 'little') + seed_id.to_bytes(4, 'little') + self.player.get_seed(seed_id).to_bytes(4, 'little')
                self.sendPacket(response)

            elif id == 'DSRL':
                # Client making a "Roll Dice" request
                assert len(payload) == 8
                perm_id = int.from_bytes(payload[0:4], byteorder='little')
                slot_id = int.from_bytes(payload[4:8], byteorder='little')
                self.logger.info("Received 'Roll Dice' request from %d:%d", perm_id, slot_id)

                response = bytes('dsRL', 'ascii') + perm_id.to_bytes(4, 'little') + slot_id.to_bytes(4, 'little') + self.player.inc_seed(slot_id).to_bytes(4, 'little')
                self.sendPacket(response)

            elif id == 'DSNM':
                # Client checking if desired name is OK.
                slot_id = int.from_bytes(payload[0:4], byteorder='little')
                name = decodeString(payload[4:])
                self.logger.info("Received 'Name OK?' request, slot=%d name=%s", slot_id, name)

                # TODO: We always approve names now, but it would be good to know
                #  which packet indicates "name no good" (dsNO?  dsNR?)
                self.player.set_name(slot_id, name)

                # the client also complains if you ack a 0-byte name, so we should not do that either
                response = bytes('dsNM', 'ascii') + slot_id.to_bytes(4, 'little') + encodeString(name)
                self.sendPacket(response)

            elif id == 'DSRI':
                # "Region Info" request - player wants to know who is in the region with them
                assert len(payload) == 8
                perm_id = int.from_bytes(payload[0:4], byteorder='little')
                region_id = int.from_bytes(payload[4:8], byteorder='little')

                # 
                response = bytes('dsRI', 'ascii') + perm_id.to_bytes(4, 'little') + region_id.to_bytes(4, 'little') + (2).to_bytes(4, 'little') + perm_id.to_bytes(4, 'little') + (12345).to_bytes(4, 'little')
                response = bytes('dsRI', 'ascii') + perm_id.to_bytes(4, 'little') + region_id.to_bytes(4, 'little') + (1).to_bytes(4, 'little') + perm_id.to_bytes(4, 'little')
                self.sendPacket(response)

            elif id == 'DSRD':
                # Client making a Read Request of something
                #  There are different types of things to Read:
                #  PCSA (save), GLRG (region?), GLOB (global?), PCIN / PCOU, and PCQK
                # but they all start with an ID...
                assert len(payload) == 24
                perm_id = int.from_bytes(payload[0:4], byteorder='little')
                rd_block = str(payload[4:8], 'ascii')

                # read of "shared" memory section, either "global" or "region"-specific
                #  there are numbered datatypes under each (e.g. each region is a different dtype)
                rd_dtype = int.from_bytes(payload[8:12], byteorder='little')
                #  "key" is an ID for the client's request, maybe for sequencing?
                rd_key = int.from_bytes(payload[12:16], byteorder='little')
                #  address and length of data block to read
                rd_addr = int.from_bytes(payload[16:20], byteorder='little')
                rd_len = int.from_bytes(payload[20:24], byteorder='little')

                self.logger.info("Received 'Read' (block=%s) request from %d: (dtype=%d, key=%d, addr=%d, len=%d)", rd_block, perm_id, rd_dtype, rd_key, rd_addr, rd_len)

                if rd_block == 'GLOB' or rd_block == 'GLRG':
                    # send bytes back by getting them from the global state holder
                    block = state.read(rd_block, rd_dtype, rd_addr, rd_len)
                    #hexdump(block)

                    # the "0" here is used for fragmenting responses, a thing we don't care to do
                    response = bytes('dsRD', 'ascii') + perm_id.to_bytes(4, 'little') + bytes(rd_block, 'ascii')+ rd_dtype.to_bytes(4, 'little') + (0).to_bytes(4, 'little') + (rd_key + 1).to_bytes(4, 'little') + rd_addr.to_bytes(4, 'little') + rd_len.to_bytes(4, 'little') + block

                elif rd_block == 'PCSA':
                    block = self.player.read(rd_addr, rd_len)
                    #hexdump(block)
                    response = bytes('dsRD', 'ascii') + perm_id.to_bytes(4, 'little') + bytes(rd_block, 'ascii')+ rd_dtype.to_bytes(4, 'little') + (0).to_bytes(4, 'little') + (rd_key + 1).to_bytes(4, 'little') + rd_addr.to_bytes(4, 'little') + rd_len.to_bytes(4, 'little') + block

                elif rd_block == 'PCIN' or rd_block == 'PCOU' or rd_block == 'PCQK':
                    block = bytes(rd_len)
                    #hexdump(block)
                    response = bytes('dsRD', 'ascii') + perm_id.to_bytes(4, 'little') + bytes(rd_block, 'ascii')+ rd_dtype.to_bytes(4, 'little') + (0).to_bytes(4, 'little') + (rd_key + 1).to_bytes(4, 'little') + rd_addr.to_bytes(4, 'little') + rd_len.to_bytes(4, 'little') + block


                self.sendPacket(response)

            elif id == 'DSWT':
                # Client making a Write Request of something
                #  There are different types of things to Write:
                #  PCSA (save), GLRG (region?), GLOB (global?), and PCQK
                # but they all start with an ID...
                #self.logger.debug("Packet received (len=%d, id=%s, payload=%s)", len(payload), id, payload)
                #hexdump(payload)

                perm_id = int.from_bytes(payload[0:4], byteorder='little')
                wt_block = str(payload[4:8], 'ascii')

                if wt_block == 'PCQK':
                    # unknown queue area
                    wt_unk1 = int.from_bytes(payload[8:12], 'little')
                    wt_unk2 = int.from_bytes(payload[12:16], 'little')
                    wt_unk3 = int.from_bytes(payload[16:20], 'little')
                    wt_addr = int.from_bytes(payload[20:24], 'little')
                    wt_len = int.from_bytes(payload[24:28], 'little')
                    assert wt_len == len(payload[28:])
                    self.logger.info("Received 'Write' (block=%s) request from %d: (unk1=%d, unk2=%d, unk3=%d, addr=%d, len=%d)", wt_block, perm_id, wt_unk1, wt_unk2, wt_unk3, wt_addr, wt_len)
                    hexdump(payload[28:])
                    
                elif wt_block == 'PCSA':
                    # trying to save character
                    wt_unk1 = int.from_bytes(payload[8:12], 'little')
                    wt_unk2 = int.from_bytes(payload[12:16], 'little')
                    wt_unk3 = int.from_bytes(payload[16:20], 'little')
                    wt_addr = int.from_bytes(payload[20:24], 'little')
                    wt_len = int.from_bytes(payload[24:28], 'little')
                    assert wt_len == len(payload[28:])
                    self.logger.info("Received 'Write' (block=%s) request from %d: (unk1=%d, unk2=%d, unk3=%d, addr=%d, len=%d)", wt_block, perm_id, wt_unk1, wt_unk2, wt_unk3, wt_addr, wt_len)
                    hexdump(payload[28:])

                    self.player.write(wt_addr, payload[28:])

                else:
                    self.logger.debug("Packet received (len=%d, id=%s, payload=%s)", len(payload), id, payload)
                    block = self.player.read(rd_addr, rd_len)
                    hexdump(payload)

                # send dummy bytes back
                #response = bytes('dsWT', 'ascii') + perm_id.to_bytes(4, 'little') + bytes(rd_block, 'ascii')
                #if rd_block == 'PCSA':
                    # truncate it for now
                    #response += (0).to_bytes(8, 'little')
                    #response += (0).to_bytes(8, 'little')
                    #response = bytes('dsRD', 'ascii') + perm_id.to_bytes(4, 'little') + bytes(rd_block, 'ascii') + rd_key.to_bytes(4, 'little') + rd_dtype.to_bytes(4, 'little') + rd_addr.to_bytes(4, 'little') + (rd_len - 1).to_bytes(4, 'little') + bytes([0 for i in range(rd_len)])
                #else:
                    #state.write(rd_block, rd_dtype, rd_addr, payload[28:])
                    #response += rd_dtype.to_bytes(4, 'little') + (0).to_bytes(4, 'little') + (rd_key + 1).to_bytes(4, 'little') + rd_addr.to_bytes(4, 'little') + rd_len.to_bytes(4, 'little')
                #self.sendPacket(response)


            else:
                self.logger.debug("Packet received (len=%d, id=%s, payload=%s)", len(payload), id, payload)
                hexdump(payload)
                self.logger.debug("Ignoring packet")

    def finish(self):
        # try dsCL see if we can get them to drop
        if self.player:
            response = bytes('dsCL', 'ascii') + self.player.id.to_bytes(4, 'little')
            self.sendPacket(response)
            self.player.save('player.pickle')


def run(argv):
    ThreadingTCPServer.allow_reuse_address = True
    server = ThreadingTCPServer((HOST, PORT), ThreadedTCPRequestHandler)
    with server:
        # run until ctrl+C pressed
        server.serve_forever()
