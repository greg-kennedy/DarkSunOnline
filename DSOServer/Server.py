import selectors
import socket
from datetime import datetime
from logging import getLogger
from os import getpid
from time import time

from .Compression import RLECompress, RLEUncompress, DecodeString, EncodeString, i32
from .State import State

logger = getLogger(__name__)


# helper funcs
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


def buildSlotResults(state, perm_id):
    # 'dsIN', 4 bytes myPermId, 4x1 byte slot permission levels
    # perm. id >= 0x80000000 gives "No host response"
    player = state.players[perm_id]

    response = bytes("dsIN", "ascii") + i32(perm_id)
    for i in range(4):
        response += bytes([player.data_slot['perm'][i]])

    # currently selected name
    response += EncodeString(player.data_slot['name'][player.data_slot['slot']])

    # all 4 player names w/ flag
    for i in range(4):
        response += i32(player.data_slot['flag'][i]) + EncodeString(player.data_slot['name'][i])

    # "Process ID"
    response += i32(getpid())

    # self.logger.debug("Sending TEN Init response")
    # hexdump(response)
    return response


# A Connection class handles connection to a client
#  Provides method to read and write - when a complete packet is "read", it takes game action
class Connection:
    __slots__ = "socket", "buf", "len", "compressed", "player"

    def __init__(self, socket):
        self.socket = socket

        # buffers for the incoming packet read
        self.buf = bytearray()
        self.len = 0
        self.compressed = False

        # tracks a player object which can be saved / loaded
        self.player = 0

    def handle(self, data, state):
        # check tag (first 4 bytes) of payload
        id, payload = str(data[0:4], "ascii"), data[4:]

        #logger.debug("Packet received (id=%s, payload=%s)", id, payload)

        # ###############
        # The two supported Launcher commands
        if id == "LAHI":
            logger.debug("Received launcher info request")

            # TODO: replace this with a user-configurable message and a real player count
            info = "==TEN TWO==\r\n\r\nDevelopment DSO server at greg-kennedy.com\r\nTotal players online: who knows?"

            response = bytes("laHI", "ascii") + EncodeString(info)

            return self.send(response, False)

        elif id == "LAUP":
            logger.debug("Received launcher username/password request")

            # TODO: replace this with calls to DecodeString
            user_len = int.from_bytes(payload[0:4], byteorder="little")
            assert payload[4 + user_len - 1] == 0
            username = str(payload[4 : 4 + user_len - 1], "ascii")

            pass_len = int.from_bytes(
                payload[4 + user_len : 4 + user_len + 4], byteorder="little"
            )
            assert payload[4 + user_len + 4 + pass_len - 1] == 0
            password = str(
                payload[4 + user_len + 4 : 4 + user_len + 4 + pass_len - 1], "ascii"
            )

            # Check login against state db
            token = state.get_login_token(username, password)
            if not token:
                logger.debug(" . Denying login")
                ok = "laNO"
                msg = "Invalid username or password.\0"
            else:
                # username and password look good!  create a login token
                #  and put it in the state for later handoff.
                logger.debug(" . Accepting login, issuing token (token=%s)", token)
                ok = "laOK"
                msg = token + "\0"

            response = bytes(ok, "ascii") + i32(len(msg)) + bytes(msg, "ascii")
            return self.send(response, False)

        #### GAME COMMANDS
        elif id == "DSIT":
            # TEN Init
            token = DecodeString(payload)
            logger.debug("Received TEN Init packet (token=%s)", token)

            # if you close the socket after receiving this packet without responding,
            #  the remote reports this as "Account still logged on".

            username = state.return_login_token(token)

            if username:
                logger.debug(" . Got valid login token (username=%s)", username)

                if state.id_by_name(username):
                    # player is already logged in!
                    return self.send( bytes('dsNI', 'ascii') , False)

                self.player = state.add_player(username)
                return self.send(buildSlotResults(state, self.player))
            else:
                logger.debug(" . Invalid login token, disconnecting")
                # Login error, kill client
                return False

        elif id == "DSLG":
            # client uploading logs to us
            #  the format is: 4 bytes string length, null-terminated ASCII string
            msg = DecodeString(payload)
            logger.debug("Received client log: %s", msg)

            # no response to this
            return True

        elif id == "DSSL":
            assert len(payload) == 0
            logger.info("Received client ping")

            response = bytes("dsSL", "ascii") + i32(int(time()))
            return self.send(response)

        elif id == "DSNS":
            # Client name selection - they want to change the current Slot
            assert len(payload) == 4
            slot_id = int.from_bytes(payload[0:4], byteorder="little")
            logger.info("Received New Slot Choice: %d", slot_id)

            state.players[self.player].data_slot['slot'] = slot_id

            # give back the player info struct again
            return self.send(buildSlotResults(state, self.player))

        elif id == "DSPS":
            # Client "set position"
            assert len(payload) == 20
            perm_id = int.from_bytes(payload[0:4], byteorder="little")
            unknown = int.from_bytes(payload[4:8], byteorder="little")
            x = int.from_bytes(payload[8:12], byteorder="little")
            y = int.from_bytes(payload[12:16], byteorder="little")
            reg = int.from_bytes(payload[16:20], byteorder="little")
            logger.info(
                "Received Set Position for %d (type %d): (x=%d, y=%d, reg=%d)",
                perm_id,
                unknown,
                x,
                y,
                reg,
            )

            state.players[self.player].set_position(x, y, reg)

            # the "response" is a collected list of positions, where "1" is the count and then the payloads are from each other packet
            response = (
                bytes("dsPS", "ascii")
                + i32(perm_id)
                + i32((1))
                + i32(perm_id)
                + i32(unknown)
                + i32(x)
                + i32(y)
                + i32(reg)
            )
            return self.send(response)

        elif id == "DSDT":
            # Client requesting Host Date
            assert len(payload) == 4
            perm_id = int.from_bytes(payload[0:4], byteorder="little")
            logger.info("Received Host Date req from %d", perm_id)

            # calculate days and seconds since Jan. 1 of this year
            #  TODO: this may be incorrect, it might be days since epoch, or seconds since, etc
            now = datetime.now()
            epoch = now.replace(
                month=1, day=1, hour=0, minute=0, second=0, microsecond=0
            )
            diff = now - epoch

            response = bytes("dsDT", "ascii") + i32(diff.seconds) + i32(diff.days)
            return self.send(response)

        elif id == "DSRS":
            # Client making a "Read Seed" request
            assert len(payload) == 8
            perm_id = int.from_bytes(payload[0:4], byteorder="little")
            slot_id = int.from_bytes(payload[4:8], byteorder="little")
            logger.info("Received 'Read Seed' (%d) request from %d", slot_id, perm_id)

            response = (
                bytes("dsRS", "ascii")
                + i32(perm_id)
                + i32(slot_id)
                + i32(state.players[self.player].data_slot['seed'][slot_id])
            )
            return self.send(response)

        elif id == "DSRL":
            # Client making a "Roll Dice" request
            assert len(payload) == 8
            perm_id = int.from_bytes(payload[0:4], byteorder="little")
            slot_id = int.from_bytes(payload[4:8], byteorder="little")
            logger.info("Received 'Roll Dice' request from %d:%d", perm_id, slot_id)

            response = (
                bytes("dsRL", "ascii")
                + i32(perm_id)
                + i32(slot_id)
                + i32(state.players[self.player].inc_seed(slot_id))
            )
            return self.send(response)

        elif id == "DSNM":
            # Client checking if desired name is OK.
            slot_id = int.from_bytes(payload[0:4], byteorder="little")
            name = DecodeString(payload[4:])
            logger.info("Received 'Name OK?' request, slot=%d name=%s", slot_id, name)

            # TODO: We always approve names now, but it would be good to know
            #  which packet indicates "name no good" (dsNO?  dsNR?)
            state.players[self.player].data_slot['name'][slot_id]

            # the client also complains if you ack a 0-byte name, so we should not do that either
            response = bytes("dsNM", "ascii") + i32(slot_id) + EncodeString(name)
            return self.send(response)

        elif id == "DSRI":
            # "Region Info" request - player wants to know who is in the region with them
            assert len(payload) == 8
            perm_id = int.from_bytes(payload[0:4], byteorder="little")
            region_id = int.from_bytes(payload[4:8], byteorder="little")
            logger.info(
                "Received Region Info request, perm_id=%d rgn=%d",
                perm_id,
                region_id,
            )

            ids = state.ids_in_region(region_id)
            logger.info(
                " There are " + str(len(ids)) + " players in region: " + str(ids)
            )

            response = (
                bytes("dsRI", "ascii")
                + i32(perm_id)
                + i32(region_id)
                + (-len(ids)).to_bytes(4, "little", signed=True)
            )
            for i in ids:
                response += i32(i)

            return self.send(response)

        elif id == "DSRD":
            # Client making a Read Request of something
            #  There are different types of things to Read:
            #  PCSA (save), GLRG (region?), GLOB (global?), PCIN / PCOU, and PCQK
            # but they all start with an ID...
            assert len(payload) == 24
            perm_id = int.from_bytes(payload[0:4], byteorder="little")
            rd_block = str(payload[4:8], "ascii")
            rd_index1 = int.from_bytes(payload[8:12], byteorder="little")
            rd_index2 = int.from_bytes(payload[12:16], byteorder="little")
            #  address and length of data block to read
            rd_addr = int.from_bytes(payload[16:20], byteorder="little")
            rd_len = int.from_bytes(payload[20:24], "little")

            logger.info(
                "Received 'Read' (block=%s) request from %d: (index1=%d, index2=%d, addr=%d, len=%d)",
                rd_block,
                perm_id,
                rd_index1,
                rd_index2,
                rd_addr,
                rd_len,
            )
            if rd_block == "GLOB":
                # read of "global" shared memory area - things like high score tables, etc
                #  each type is numbered differently, there are 0x16 of them
                assert rd_index2 == 0

                # send bytes back by getting them from the global state holder
                block = state.read_glob(rd_index1, rd_addr, rd_len)

            elif rd_block == "GLRG":
                # read of "region" shared memory area - things like objects, items, etc
                # data type, 0-5 or so (actually client usually requests 6?  weird)
                block = state.read_glrg(rd_index1, rd_index2, rd_addr, rd_len)

            elif rd_block == "PCSA":
                # Player save file info.  These don't have multiple subsections.  Also you should only read your own data.
                assert rd_index1 == 0
                assert rd_index2 == 0
                #  address and length of data block to read
                block = state.players[self.player].read("PCSA", rd_addr, rd_len)

            elif rd_block == "PCIN" or rd_block == "PCOU" or rd_block == "PCQK":
                # read of "global" shared memory area - things like high score tables, etc
                #  each type is numbered differently, there are 0x16 of them
                # Stub these in for now with all-0
                assert rd_index2 == 0
                block = state.players[rd_index1].read(rd_block, rd_addr, rd_len)

            else:
                assert False

            key = 1
            response = (
                bytes("dsRD", "ascii")
                + i32(perm_id)
                + bytes(rd_block, "ascii")
                + i32(rd_index1)
                + i32(rd_index2)
                + i32(key)
                + i32(rd_addr)
                + i32(rd_len)
                + block
            )
            return self.send(response)

        elif id == "DSWQ":
            # Client making a Write Request of some shared memory segment, GLOB or GLRG.
            #  Since this could be contentious, it expects back a dsWT (write OK)
            #  or a dsWE (write Error)
            # The client calls this a "useBroadcast" write
            perm_id = int.from_bytes(payload[0:4], byteorder="little")
            wt_block = str(payload[4:8], "ascii")
            wt_index1 = int.from_bytes(payload[8:12], byteorder="little")
            wt_index2 = int.from_bytes(payload[12:16], byteorder="little")
            # key SHOULD likely be used to resolve race conditions, but it's always 0 in 1.0
            wt_key = int.from_bytes(payload[16:20], byteorder="little")
            assert wt_key == 0
            #  address and length of data block to write
            wt_addr = int.from_bytes(payload[20:24], byteorder="little")
            wt_len = int.from_bytes(payload[24:28], "little")
            assert wt_len == len(payload[28:])
            logger.info(
                "Received 'Write Broadcast' (block=%s) request from %d: (index1=%d, index2=%d, key=%d, addr=%d, len=%d)",
                wt_block,
                perm_id,
                wt_index1,
                wt_index2,
                wt_key,
                wt_addr,
                wt_len,
            )

            if wt_block == "GLOB":
                # write of "global" shared memory area - should never have an index2 set
                assert wt_index2 == 0
                success = state.write_glob(wt_index1, wt_addr, payload[28:])
            elif wt_block == "GLRG":
                # write of "region" shared memory area
                success = state.write_glrg(wt_index1, wt_index2, wt_addr, payload[28:])
            else:
                assert False

            # ack or nack this
            if success:
                response = bytes("dsWT", "ascii")
            else:
                response = bytes("dsWE", "ascii")

            key = 1
            response += (
                i32(perm_id)
                + bytes(wt_block, "ascii")
                + i32(wt_index1)
                + i32(wt_index2)
                + i32(key)
                + i32(wt_len)
            )
            return self.send(response)

        elif id == "DSWT":
            # Client making a Write Request of something
            #  There are different types of things to Write:
            #  PCSA (save), PCQK, PCIN and PCOU
            perm_id = int.from_bytes(payload[0:4], byteorder="little")
            wt_block = str(payload[4:8], "ascii")
            wt_index1 = int.from_bytes(payload[8:12], byteorder="little")
            wt_index2 = int.from_bytes(payload[12:16], byteorder="little")
            # key SHOULD likely be used to resolve race conditions, but it's always 0 in 1.0
            wt_key = int.from_bytes(payload[16:20], byteorder="little")
            assert wt_key == 0
            #  address and length of data block to write
            wt_addr = int.from_bytes(payload[20:24], byteorder="little")
            wt_len = int.from_bytes(payload[24:28], "little")
            assert wt_len == len(payload[28:])

            logger.info(
                "Received 'Write Player Char' (block=%s) request from %d: (index1=%d, index2=%d, key=%d, addr=%d, len=%d)",
                wt_block,
                perm_id,
                wt_index1,
                wt_index2,
                wt_key,
                wt_addr,
                wt_len,
            )

            if wt_block == "PCSA":
                # trying to save character - everything is ignored except the address and payload
                assert wt_index1 == 0
                assert wt_index2 == 0
                state.players[self.player].write("PCSA", wt_addr, payload[28:])

            elif wt_block == "PCIN" or wt_block == "PCOU" or wt_block == "PCQK":
                # trying to write to someone's 'outbox'
                if wt_index1 == 0:
                    wt_index1 = self.player
                assert wt_index2 == 0
                state.players[wt_index1].write(wt_block, wt_addr, payload[28:])

            else:
                hexdump(payload)

            return True

        else:
            logger.debug(
                "Packet received (len=%d, id=%s, payload=%s)",
                len(payload),
                id,
                payload,
            )
            hexdump(payload)
            logger.debug("Ignoring packet")
            return True

    # helper to send a packet to the connected client
    #  it tries RLE compression for size reduction, and prepends the length as well
    def send(self, data, allow_compress=True):
        if allow_compress:
            compressed = RLECompress(data)
            if len(compressed) < len(data):
                pkt = ((2 + len(compressed)) | 0x8000).to_bytes(
                    2, "little"
                ) + compressed
            else:
                pkt = (2 + len(data)).to_bytes(2, "little") + data
        else:
            pkt = (2 + len(data)).to_bytes(2, "little") + data

        if len(pkt) < self.socket.send(pkt):
            # Failed to send all the bytes, which means the client disconnected, or the send-buffer is full.
            #  It's possible to await EVENT_SEND and send the rest; however, a full send-buffer means a
            #  significant backlog of packets, and it's probably just as well to disconnect them.
            return False
        return True

    def recv(self, state):
        """Read helper for packets - consumes some bytes and triggers the packet handler if done"""

        # read time!  get 2 bytes, then N bytes
        if self.len == 0:
            buf = self.socket.recv(2 - len(self.buf))
            if not buf:
                # 0-byte response here means the client disconnected.
                return False
            else:
                # got at least one byte, append it to our read-buffer
                self.buf += buf
                if len(self.buf) == 2:
                    # got our 2 bytes, now we expect len - 2 more bytes
                    pkt_len = int.from_bytes(self.buf, byteorder="little")
                    self.compressed = pkt_len & 0x8000
                    self.len = (pkt_len & 0x7FFF) - 2
                    self.buf.clear()

        else:
            buf = self.socket.recv(self.len - len(self.buf))
            if not buf:
                # 0-byte response here means the client disconnected.
                return False
            else:
                self.buf += buf
                if len(self.buf) == self.len:
                    if not self.handle(
                        RLEUncompress(self.buf) if self.compressed else self.buf,
                        state,
                    ):
                        return False

                    self.len = 0
                    self.buf.clear()

        return True

    def close(self, state):
        # try dsCL see if we can get them to drop
        if self.player:
            state.drop_player(self.player)
            response = bytes("dsCL", "ascii") + i32(self.player)
            self.send(response)

        # close socket
        self.socket.close()


class Server:
    __slots__ = "address_port", "database"

    def __init__(self, address_port, database):
        # Save the address / port for server launch (below)
        self.address_port = address_port
        self.database = database

    def run(self):
        """Runs the server."""

        # Create world-state and attach it to the database connection
        state = State(self.database)

        # map of all connected clients
        connections = {}

        # get a listen socket, IPV4-only
        logger.info(f"Opening listen socket on {self.address_port}")
        sock_listen = socket.create_server(self.address_port)
        sock_listen.setblocking(False)

        # create a selectors object and register listen socket in it
        sel = selectors.DefaultSelector()
        sel.register(sock_listen, selectors.EVENT_READ)
        logger.info("Awaiting incoming connections")

        # main server loop
        running = True
        while running:
            try:
                events = sel.select()
                for key, mask in events:
                    if key.fileobj == sock_listen:
                        # activity on the listen-socket is a new connection we can accept
                        #  TODO: accept() can fail, which may raise an exception... I think
                        conn, addr = sock_listen.accept()

                        logger.info(
                            f"Received new incoming connection from {addr}: {conn}"
                        )

                        # Wrap the socket in a Connection object and add to the connections dict
                        conn.setblocking(False)
                        conn_obj = Connection(conn)
                        connections[conn.fileno()] = conn_obj

                        # request notif. of future bytes available for reading
                        sel.register(conn, selectors.EVENT_READ)
                    else:
                        # activity on a different socket
                        if mask & selectors.EVENT_READ:
                            c = connections[key.fd]
                            if not c.recv(state):
                                logger.info(f"Dropping connection {key}")
                                # do not notify about this again
                                sel.unregister(key.fileobj)
                                # drop conn from list
                                c.close(state)
                                del connections[key.fd]

            except Exception as e:
                print("Got an error: ", e)
                running = False

        # great, done running, shut everything down
        sel.close()

        for c in connections:
            c.close()

        sock_listen.close()

        state.close()
