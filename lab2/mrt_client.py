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
from mrt_timer import Timer

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

        # send tracking for stop-and-wait
        self.send_base = 0
        self.send_end = 0
        self.seg_dict = {}  # seq_num -> payload bytes
        self.timer = Timer(timeout=0.5)

        # events for blocking calls
        self.connect_event = threading.Event()
        self.all_acked_event = threading.Event()

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
        self.timer.start()

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
        self.all_acked_event.clear()
        if not isinstance(data, bytes):
            data = data.encode()
        total = len(data)

        with self.lock:
            # fragment data into segments
            self.seg_dict = {}
            offset = 0
            while offset < total:
                chunk = data[offset:offset + self.max_payload]
                abs_seq = self.seq_num + offset
                self.seg_dict[abs_seq] = chunk
                offset += len(chunk)

            self.send_base = self.seq_num
            self.next_seq_num = self.seq_num
            self.send_end = self.seq_num + total

        # block until all segments are acked
        self.all_acked_event.wait()

        with self.lock:
            self.seq_num += total
        return total

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
        incoming segments. Handles handshake, data ACKs, and
        retransmits on timeout.
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

            # send data + check timeouts
            with self.lock:
                if self.state == 'CONNECTING':
                    self._check_syn_timeout()
                elif self.state == 'ESTABLISHED':
                    self._send_next_segment()
                    self._check_data_timeout()

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
                    self.timer.stop()
                    self.connect_event.set()

            elif self.state == 'ESTABLISHED':
                if seg.has_flag(ACK):
                    if seg.ack_num > self.send_base:
                        # cumulative ack, advance base
                        self.send_base = seg.ack_num
                        self.peer_rwnd = seg.rwnd
                        if self.send_base >= self.send_end:
                            # all data acked
                            self.timer.stop()
                            self.all_acked_event.set()
                        else:
                            # restart timer for remaining data
                            self.timer.reset()

    def _send_next_segment(self):
        """
        Send the next unsent segment (stop-and-wait). Only sends
        if the previous segment was acked.
        """
        if (self.send_base < self.send_end
                and self.next_seq_num == self.send_base
                and self.next_seq_num in self.seg_dict):
            payload = self.seg_dict[self.next_seq_num]
            seg = Segment(
                self.src_port, self.dst_port,
                seq_num=self.next_seq_num, ack_num=self.ack_num,
                flags=DATA | ACK, rwnd=0, payload=payload
            )
            self.sock.sendto(
                seg.to_bytes(), (self.dst_addr, self.dst_port)
            )
            self.next_seq_num += len(payload)
            self.timer.start()

    def _check_data_timeout(self):
        """
        If timeout expired, retransmit from send_base.
        """
        if self.timer.is_expired() and self.send_base < self.send_end:
            self.next_seq_num = self.send_base
            self.timer.start()

    def _check_syn_timeout(self):
        """
        Retransmit SYN if timeout expired during handshake.
        """
        if self.timer.is_expired():
            syn = Segment(
                self.src_port, self.dst_port,
                seq_num=0, ack_num=0, flags=SYN, rwnd=0
            )
            self.sock.sendto(
                syn.to_bytes(), (self.dst_addr, self.dst_port)
            )
            self.timer.start()
