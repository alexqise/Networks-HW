#
# Columbia University - CSEE 4119 Computer Networks
# Assignment 2 - Mini Reliable Transport Protocol
#
# mrt_server.py - defining server APIs of the mini reliable transport
# protocol
#

import socket # for UDP connection
import threading
import queue

from mrt_segment import Segment, HEADER_SIZE, SYN, ACK, FIN, DATA

#
# Server
#
class Server:
    def init(self, src_port, receive_buffer_size):
        """
        initialize the server, create the UDP connection, and configure the receive buffer

        arguments:
        src_port -- the port the server is using to receive segments
        receive_buffer_size -- the maximum size of the receive buffer
        """
        self.src_port = src_port
        self.receive_buffer_size = receive_buffer_size

        # create and bind UDP socket (blocking for rcv_handler)
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.bind(('', src_port))

        # connection state
        self.state = 'LISTEN'
        self.client_addr = None
        self.lock = threading.Lock()
        self.running = True

        # buffers
        # receive_buffer: raw segments from rcv_handler -> sgmnt_handler
        self.receive_buffer = queue.Queue()
        # data_buffer: in-order app data for receive() to read from
        self.data_buffer = bytearray()
        self.data_cond = threading.Condition(self.lock)

        # spawn handler threads
        self.rcv_thread = threading.Thread(
            target=self._rcv_handler, daemon=True
        )
        self.sgmnt_thread = threading.Thread(
            target=self._sgmnt_handler, daemon=True
        )
        self.rcv_thread.start()
        self.sgmnt_thread.start()

    def accept(self):
        """
        accept a client request
        blocking until a client is accepted

        it should support protection against segment loss/corruption/reordering

        return:
        the connection to the client
        """
        # phase 3: just wait until we know who the client is
        while self.client_addr is None:
            pass
        return self.client_addr

    def receive(self, conn, length):
        """
        receive data from the given client
        blocking until the requested amount of data is received

        it should support protection against segment loss/corruption/reordering
        the client should never overwhelm the server given the receive buffer size

        arguments:
        conn -- the connection to the client
        length -- the number of bytes to receive

        return:
        data -- the bytes received from the client, guaranteed to be in its original order
        """
        # block until we have enough data
        with self.data_cond:
            while len(self.data_buffer) < length:
                self.data_cond.wait()
            data = bytes(self.data_buffer[:length])
            del self.data_buffer[:length]
        return data

    def close(self):
        """
        close the server and the client if it is still connected
        blocking until the connection is closed
        """
        self.running = False
        self.sock.close()

    def _rcv_handler(self):
        """
        Receive thread: reads from the socket and puts valid
        segments into the receive_buffer queue.
        """
        while self.running:
            try:
                raw, addr = self.sock.recvfrom(65535)
                seg = Segment.from_bytes(raw)
                if seg is None:
                    continue  # corrupt, drop
                self.receive_buffer.put((seg, addr))
            except OSError:
                break  # socket closed

    def _sgmnt_handler(self):
        """
        Segment handler thread: processes segments from the
        receive_buffer and puts app data into data_buffer.
        """
        while self.running:
            try:
                seg, addr = self.receive_buffer.get(timeout=0.1)
            except queue.Empty:
                continue

            with self.data_cond:
                # remember who the client is
                if self.client_addr is None:
                    self.client_addr = addr

                # phase 3: just dump payload into data_buffer
                if seg.has_flag(DATA) and seg.payload_length > 0:
                    self.data_buffer.extend(seg.payload)
                    self.data_cond.notify_all()
