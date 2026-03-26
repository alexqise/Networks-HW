#
# Columbia University - CSEE 4119 Computer Networks
# Assignment 2 - Mini Reliable Transport Protocol
#
# mrt_client.py - defining client APIs of the mini reliable transport
# protocol
#

import socket # for UDP connection
import threading

from mrt_segment import Segment, HEADER_SIZE, SYN, ACK, FIN, DATA

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
        self.lock = threading.Lock()
        self.running = True

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
        pass

    def send(self, data):
        """
        send a chunk of data of arbitrary size to the server
        blocking until all data is sent

        it should support protection against segment loss/corruption/reordering and flow control

        arguments:
        data -- the bytes to be sent to the server
        """
        # phase 3: just send raw segments through the handler for now
        offset = 0
        while offset < len(data):
            chunk = data[offset:offset + self.max_payload]
            seg = Segment(
                self.src_port, self.dst_port,
                seq_num=offset, ack_num=0,
                flags=DATA, rwnd=0, payload=chunk
            )
            self.sock.sendto(seg.to_bytes(), (self.dst_addr, self.dst_port))
            offset += len(chunk)
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
        incoming segments. For now just prints what it gets.
        """
        while self.running:
            try:
                raw, addr = self.sock.recvfrom(65535)
                seg = Segment.from_bytes(raw)
                if seg is None:
                    continue  # corrupt, drop
                with self.lock:
                    print(f"[client] got {seg.type_str()} seq={seg.seq_num} ack={seg.ack_num}")
            except (socket.timeout, BlockingIOError, OSError):
                pass
