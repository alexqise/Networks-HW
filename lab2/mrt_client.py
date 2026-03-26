#
# Columbia University - CSEE 4119 Computer Networks
# Assignment 2 - Mini Reliable Transport Protocol
#
# mrt_client.py - defining client APIs of the mini reliable transport
# protocol
#

import socket # for UDP connection
import threading
import time

from mrt_segment import Segment, HEADER_SIZE, SYN, ACK, FIN, DATA

# retransmission timeout in seconds
TIMEOUT = 0.5

class Client:
    def init(self, src_port, dst_addr, dst_port, segment_size):
        """
        initialize the client and create the client UDP channel

        arguments:
        src_port -- the port the client is using to send segments
        dst_addr -- the address of the server/network simulator
        dst_port -- the port of the server/network simulator
        segment_size -- the maximum size of a segment (including the header)
        """
        self.src_port = src_port
        self.dst_addr = dst_addr
        self.dst_port = dst_port
        self.segment_size = segment_size
        self.max_payload = segment_size - HEADER_SIZE

        # create and bind UDP socket
        # short timeout so the handler thread can interleave send/recv
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.bind(('', src_port))
        self.sock.settimeout(0.01)

        # connection state
        self.state = 'CLOSED'
        self.seq_num = 0
        self.ack_num = 0
        self.peer_rwnd = 0
        self.lock = threading.Lock()
        self.running = True

        # events for blocking calls
        self.connect_event = threading.Event()

        # spawn handler thread
        self.handler_thread = threading.Thread(
            target=self._rcv_and_sgmnt_handler, daemon=True
        )
        self.handler_thread.start()

    def connect(self):
        """
        connect to the server
        blocking until the connection is established

        it should support protection against segment loss/corruption/reordering
        """
        with self.lock:
            self.state = 'CONNECTING'
            self.seq_num = 0

        # send initial SYN, handler thread will retransmit on timeout
        syn = Segment(
            self.src_port, self.dst_port,
            seq_num=0, ack_num=0, flags=SYN, rwnd=0
        )
        self.sock.sendto(syn.to_bytes(), (self.dst_addr, self.dst_port))

        with self.lock:
            self.syn_send_time = time.time()

        # block until handshake completes
        self.connect_event.wait()

    def send(self, data):
        """
        send a chunk of data of arbitrary size to the server
        blocking until all data is sent

        it should support protection against segment loss/corruption/reordering and flow control

        arguments:
        data -- the bytes to be sent to the server
        """
        # phase 4: still simple send, no sliding window yet
        offset = 0
        while offset < len(data):
            chunk = data[offset:offset + self.max_payload]
            seg = Segment(
                self.src_port, self.dst_port,
                seq_num=self.seq_num + offset, ack_num=self.ack_num,
                flags=DATA | ACK, rwnd=0, payload=chunk
            )
            self.sock.sendto(seg.to_bytes(), (self.dst_addr, self.dst_port))
            offset += len(chunk)
        self.seq_num += len(data)
        return len(data)

    def close(self):
        """
        request to close the connection with the server
        blocking until the connection is closed
        """
        self.running = False
        self.sock.close()

    def _rcv_and_sgmnt_handler(self):
        """
        Handler thread that continuously receives and processes
        incoming segments. Handles SYN-ACK during handshake and
        retransmits SYN on timeout.
        """
        while self.running:
            # try to receive
            try:
                raw, addr = self.sock.recvfrom(65535)
                seg = Segment.from_bytes(raw)
                if seg is None:
                    continue  # corrupt, drop
                self._handle_segment(seg)
            except (socket.timeout, BlockingIOError, OSError):
                pass

            # check for timeouts
            with self.lock:
                if self.state == 'CONNECTING':
                    if time.time() - self.syn_send_time > TIMEOUT:
                        # retransmit SYN
                        syn = Segment(
                            self.src_port, self.dst_port,
                            seq_num=0, ack_num=0, flags=SYN, rwnd=0
                        )
                        self.sock.sendto(
                            syn.to_bytes(),
                            (self.dst_addr, self.dst_port)
                        )
                        self.syn_send_time = time.time()

    def _handle_segment(self, seg):
        """
        Process a received segment based on current state.
        """
        with self.lock:
            if self.state == 'CONNECTING':
                if seg.has_flag(SYN) and seg.has_flag(ACK):
                    # got SYN-ACK, send final ACK
                    self.ack_num = seg.seq_num + 1
                    self.seq_num = 1  # SYN consumed 1 seq number
                    self.peer_rwnd = seg.rwnd
                    ack = Segment(
                        self.src_port, self.dst_port,
                        seq_num=self.seq_num, ack_num=self.ack_num,
                        flags=ACK, rwnd=0
                    )
                    self.sock.sendto(
                        ack.to_bytes(),
                        (self.dst_addr, self.dst_port)
                    )
                    self.state = 'ESTABLISHED'
                    self.connect_event.set()
