import socket
import struct
import logging
from time import time
import datetime
from socketserver import ThreadingTCPServer, BaseRequestHandler

from .compression import RLECompress, RLEUncompress

# listen on any interface, port 14902
HOST = ''
PORT = 14902

logging.basicConfig(level=logging.NOTSET)
logger = logging.getLogger(__name__)


class ThreadedTCPRequestHandler(BaseRequestHandler):
    def setup(self):
        self.logger = logger.getChild("{}:{}".format(*self.client_address))

    # a packet!
    def handle(self):

        # helper to send a packet to the connected client
        #  it tries RLE compression for size reduction, and prepends the length as well
        def sendPacket(data):
            compressed = RLECompress(data)
            if len(compressed) < len(data):
                pkt = ((2 + len(compressed)) | 0x8000).to_bytes(2, 'little') + compressed
            else:
                pkt = (2 + len(data)).to_bytes(2, 'little') + data

            #self.logger.debug("Sending %scompressed packet %s", "" if pkt[1] & 0x80 else "UN", pkt)
            self.request.sendall(pkt)

        while 1:
            # get 2 bytes of length
            length = int.from_bytes(self.request.recv(2, socket.MSG_WAITALL), byteorder='little')
            if not length:
                # client disconnect
                break

            # top bit of length indicates compression
            compressed = (length & 0x8000)
            length &= 0x7FFF

            # read and uncompress remaining bytes
            payload = self.request.recv(length - 2, socket.MSG_WAITALL)
            if not payload:
                # client disconnect
                break

            if compressed:
                payload = RLEUncompress(payload)

            # check tag (first 4 bytes) of payload
            id = str(payload[:4], 'ascii')

            #self.logger.debug("Packet received (len=%d, id=%s, payload=%s)", length, id, payload[4:])
            if id == 'DSLG':
                # client uploading logs to us
                #  the format is: 4 bytes string length, null-terminated ASCII string
                length = int.from_bytes(payload[4:8], byteorder='little') - 1
                message = str(payload[8:(8 + length)], 'ascii')
                # check null-terminator
                assert payload[8 + length:] == bytes([0])
                self.logger.info("Received client log: %s", message)

            elif id == 'DSSL':
                self.logger.info("Received client ping")
                response = bytes('dsSL', 'ascii') + int(time()).to_bytes(4, 'little')
                sendPacket(response)

            elif id == 'DSIT':
                # TEN Init
                self.logger.debug("Received TEN Init packet")

                # If the user is already logged in, respond 'dsNI' instead
                #response = bytes('dsNI', 'ascii')

                # 'dsIN', 4 bytes myPermId, 4x1 byte slot permission levels
                # perm. id >= 0x80000000 gives "No host response"
                response = bytes('dsIN', 'ascii') + (77777777).to_bytes(4, 'little') + bytes([1, 1, 1, 1])
                #                      length,             account name?  "Cathryn"
                response += bytes([0x8, 0x0, 0x0, 0x0, 0x43, 0x61, 0x74, 0x68, 0x72, 0x79, 0x6E, 0x0])
                # 4 player names - unknown uint32, length, null-string
                #                        ???  6bytes                "Larry"
                response += bytes([1, 0, 0, 0, 0x6, 0x0, 0x0, 0x0, 0x4C, 0x61, 0x72, 0x72, 0x79, 0x00])
                #                        ???  6bytes              "Curly"
                response += bytes([1, 0, 0, 0, 0x6, 0x0, 0x0, 0x0, 0x43, 0x75, 0x72, 0x6C, 0x79, 0x00])
                #                       ???  4bytes                 "Moe"
                response += bytes([1, 0, 0, 0, 0x4, 0x0, 0x0, 0x0, 0x4D, 0x6F, 0x65, 0x00])
                #                        ???  6bytes              "Shemp"
                response += bytes([1, 0, 0, 0, 0x6, 0x0, 0x0, 0x0, 0x53, 0x68, 0x65, 0x6D, 0x70, 0x00])
                # "Process ID"
                response += bytes([1, 0, 0, 0])

                self.logger.debug("Sending TEN Init response")
                sendPacket(response)

                # try dsCL see if we can get them to drop
                #response = bytes('dsCL', 'ascii') + (9).to_bytes(4, 'little')
                #sendPacket(response)
                #response = bytes('dsCL', 'ascii') + (1).to_bytes(4, 'little')
                #response = bytes('dsNI', 'ascii')
                #sendPacket(response)
            elif id == 'DSNS':
                # Client name selection (?)
                name_id = int.from_bytes(payload[4:8], byteorder='little')
                self.logger.info("Received Name Selection: %d", name_id)

            elif id == 'DSPS':
                # Client "set position"
                perm_id = int.from_bytes(payload[4:8], byteorder='little')
                unknown = int.from_bytes(payload[8:12], byteorder='little')
                x = int.from_bytes(payload[12:16], byteorder='little')
                y = int.from_bytes(payload[16:20], byteorder='little')
                reg = int.from_bytes(payload[20:24], byteorder='little')
                self.logger.info("Received Set Position for %d (type %d): (x=%d, y=%d, reg=%d)", perm_id, unknown, x, y, reg)

            elif id == 'DSDT':
                # Client requesting Host Date
                perm_id = int.from_bytes(payload[4:8], byteorder='little')
                #date = time.gmtime(int.from_bytes(payload[4:8], byteorder='little'))
                self.logger.info("Received Host Date req from %d", perm_id)

                # calculate days and seconds since Jan. 1 of this year
                now = datetime.datetime.now()
                epoch = now.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
                diff = now - epoch

                response = bytes('dsDT', 'ascii') + diff.seconds.to_bytes(4, 'little') + diff.days.to_bytes(4, 'little')
                sendPacket(response)
                #response = bytes('dsHS', 'ascii') + (6).to_bytes(4, 'little') + bytes('Hello\0', 'ascii')
                #sendPacket(response)


            elif id == 'DSRS':
                # Client making a "Read Seed" request
                perm_id = int.from_bytes(payload[4:8], byteorder='little')
                seed_id = int.from_bytes(payload[8:12], byteorder='little')
                self.logger.info("Received 'Read Seed' (%d) request from %d", seed_id, perm_id)

            elif id == 'DSRD':
                # Client making a Read Request of something
                #  There are different types of things to Read:
                #  PCSA (save), GLRG (region?), GLOB (global?), PCIN / PCOU, and PCQK
                # but they all start with an ID...
                perm_id = int.from_bytes(payload[4:8], byteorder='little')
                rd_block = str(payload[8:12], 'ascii')
                rd_dtype = int.from_bytes(payload[12:16], byteorder='little')
                rd_key = 1 #int.from_bytes(payload[16:20], byteorder='little')
                rd_addr = int.from_bytes(payload[20:24], byteorder='little')
                rd_len = int.from_bytes(payload[24:28], byteorder='little')
                self.logger.info("Received 'Read' (block=%s) request from %d: (dtype=%d, key=%d, addr=%d, len=%d)", rd_block, perm_id, rd_dtype, rd_key, rd_addr, rd_len)

                # send dummy bytes back
                response = bytes('dsRD', 'ascii') + perm_id.to_bytes(4, 'little') + bytes(rd_block, 'ascii')
                if rd_block == 'PCSA':
                    # truncate it for now
                    response += (0).to_bytes(8, 'little')
                    response += (0).to_bytes(8, 'little')
                    #response = bytes('dsRD', 'ascii') + perm_id.to_bytes(4, 'little') + bytes(rd_block, 'ascii') + rd_key.to_bytes(4, 'little') + rd_dtype.to_bytes(4, 'little') + rd_addr.to_bytes(4, 'little') + (rd_len - 1).to_bytes(4, 'little') + bytes([0 for i in range(rd_len)])
                else:
                    response += rd_dtype.to_bytes(4, 'little') + (0).to_bytes(4, 'little') + rd_key.to_bytes(4, 'little') + rd_addr.to_bytes(4, 'little') + rd_len.to_bytes(4, 'little') + bytes([0 for i in range(rd_len)])
                sendPacket(response)


            else:
                self.logger.debug("Packet received (len=%d, id=%s, payload=%s)", length, id, payload[4:])
                self.logger.debug("Ignoring packet")


def run(argv):
    ThreadingTCPServer.allow_reuse_address = True
    server = ThreadingTCPServer((HOST, PORT), ThreadedTCPRequestHandler)
    with server:
        # run until ctrl+C pressed
        server.serve_forever()
