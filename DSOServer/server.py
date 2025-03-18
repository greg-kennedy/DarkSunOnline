import socket
import logging
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
                pkt = (len(compressed) | 0x8000).to_bytes(2, 'little') + compressed
            else:
                pkt = len(data).to_bytes(2, 'little') + data

            self.logger.debug("Sending %scompressed packet %s", "" if pkt[1] & 0x80 else "UN", pkt)
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

            self.logger.debug("Packet received (len=%d, id=%s, payload=%s)", length, id, payload[4:])

            match id:
                case 'DSLG':
                    # client uploading logs to us
                    self.logger.info("Received client log: {}", str(payload[4:], 'ascii'))
                case 'DSIT':
                    # TEN Init
                    self.logger.debug("Received TEN Init packet")

                    # This is a canned (incorrect!) login message that gets you to the loading screen
                    response = bytes([0x64, 0x73, 0x49, 0x4e, 0x1, 0x0, 0x0, 0x0, 0x1, 0x1, 0x1, 0x1, 0xa, 0x0, 0x0, 0x0, 0x35, 0x37, 0x30, 0x38, 0x38, 0x30, 0x31, 0x36, 0x34, 0x0, 0x1, 0x0, 0x0, 0x0, 0xa, 0x0, 0x0, 0x0, 0x35, 0x37, 0x30, 0x38, 0x38, 0x30, 0x31, 0x36, 0x34, 0x0, 0x0, 0x0, 0x0, 0x0, 0x1, 0x0, 0x0, 0x0, 0x0, 0x0, 0x0, 0x0, 0x0, 0x1, 0x0, 0x0, 0x0, 0x0, 0x0, 0x0, 0x0, 0x0, 0x1, 0x0, 0x0, 0x0, 0x0, 0x1, 0x0, 0x0, 0x0])

                    self.logger.debug("Sending TEN Init response")
                    sendPacket(response)

                case _:
                    self.logger.debug("Ignoring packet")


def run(argv):
    ThreadingTCPServer.allow_reuse_address = True
    server = ThreadingTCPServer((HOST, PORT), ThreadedTCPRequestHandler)
    with server:
        # run until ctrl+C pressed
        server.serve_forever()
