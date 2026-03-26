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
import datetime

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
        self.client_port = None
        self.expected_seq_num = 0
        self.lock = threading.Lock()
        self.running = True

        # events for blocking calls
        self.connect_event = threading.Event()
        self.close_event = threading.Event()

        # buffers
        # receive_buffer: raw segments from rcv_handler -> sgmnt_handler
        self.receive_buffer = queue.Queue()
        # data_buffer: in-order app data for receive() to read from
        self.data_buffer = bytearray()
        self.data_cond = threading.Condition(self.lock)

        # logging
        self.log_file = open(f"log_{src_port}.txt", "w")

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
        # block until 3-way handshake completes
        self.connect_event.wait()
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
        # wait for FIN exchange if still connected
        if self.state not in ('CLOSED', 'LISTEN'):
            self.close_event.wait(timeout=10)
        self.running = False
        self.sock.close()
        self.log_file.close()

    def _send_seg(self, seg, addr):
        """
        Send a segment over the socket and log it.
        """
        self.sock.sendto(seg.to_bytes(), addr)
        self._log(seg)

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
        receive_buffer. Handles handshake, data, and teardown.
        """
        while self.running:
            try:
                seg, addr = self.receive_buffer.get(timeout=0.1)
            except queue.Empty:
                continue

            self._log(seg)

            with self.data_cond:
                if self.state == 'LISTEN':
                    self._handle_listen(seg, addr)

                elif self.state == 'SYN_RCVD':
                    self._handle_syn_rcvd(seg, addr)

                elif self.state == 'ESTABLISHED':
                    self._handle_established(seg, addr)

                elif self.state == 'FIN_RCVD':
                    self._handle_fin_rcvd(seg, addr)

    def _handle_listen(self, seg, addr):
        """
        Handle segments in LISTEN state. If we get a SYN,
        send SYN-ACK and move to SYN_RCVD.
        """
        if seg.has_flag(SYN):
            self.client_addr = addr
            self.client_port = seg.src_port
            self.expected_seq_num = seg.seq_num + 1  # SYN consumes 1
            self.state = 'SYN_RCVD'

            syn_ack = Segment(
                self.src_port, seg.src_port,
                seq_num=0, ack_num=self.expected_seq_num,
                flags=SYN | ACK,
                rwnd=self.receive_buffer_size
            )
            self._send_seg(syn_ack, addr)

    def _handle_syn_rcvd(self, seg, addr):
        """
        Handle segments in SYN_RCVD state. If we get ACK,
        handshake is done. If duplicate SYN, resend SYN-ACK.
        If DATA arrives, treat as implicit ACK.
        """
        if seg.has_flag(SYN) and not seg.has_flag(ACK):
            # duplicate SYN, resend SYN-ACK
            syn_ack = Segment(
                self.src_port, seg.src_port,
                seq_num=0, ack_num=self.expected_seq_num,
                flags=SYN | ACK,
                rwnd=self.receive_buffer_size
            )
            self._send_seg(syn_ack, addr)

        elif seg.has_flag(ACK):
            # handshake complete
            self.state = 'ESTABLISHED'
            self.connect_event.set()
            # if this ACK also has data, process it
            if seg.has_flag(DATA):
                self._process_data(seg, addr)

        elif seg.has_flag(DATA):
            # data without ACK flag = implicit handshake done
            self.state = 'ESTABLISHED'
            self.connect_event.set()
            self._process_data(seg, addr)

    def _handle_established(self, seg, addr):
        """
        Handle segments in ESTABLISHED state. Process data
        segments or start teardown on FIN.
        """
        if seg.has_flag(DATA):
            self._process_data(seg, addr)
        elif seg.has_flag(FIN):
            self._handle_fin(seg, addr)

    def _handle_fin(self, seg, addr):
        """
        Handle a FIN from the client. Send FIN-ACK and
        move to FIN_RCVD.
        """
        self.state = 'FIN_RCVD'
        fin_ack = Segment(
            self.src_port, seg.src_port,
            seq_num=0, ack_num=seg.seq_num + 1,
            flags=FIN | ACK, rwnd=0
        )
        self._send_seg(fin_ack, addr)

    def _handle_fin_rcvd(self, seg, addr):
        """
        Handle segments in FIN_RCVD state. If we get the
        final ACK, we're done. If duplicate FIN, resend
        FIN-ACK.
        """
        if seg.has_flag(ACK) and not seg.has_flag(FIN):
            self.state = 'CLOSED'
            self.close_event.set()
        elif seg.has_flag(FIN):
            # duplicate FIN, resend FIN-ACK
            fin_ack = Segment(
                self.src_port, seg.src_port,
                seq_num=0, ack_num=seg.seq_num + 1,
                flags=FIN | ACK, rwnd=0
            )
            self._send_seg(fin_ack, addr)

    def _process_data(self, seg, addr):
        """
        Process a data segment. Only accepts in-order segments
        (seq_num == expected). Sends cumulative ACK either way.
        """
        if (seg.seq_num == self.expected_seq_num
                and seg.payload_length > 0):
            self.data_buffer.extend(seg.payload)
            self.expected_seq_num += seg.payload_length
            self.data_cond.notify_all()

        # always send cumulative ack with current rwnd
        # with GBN the receiver doesn't buffer out-of-order segments,
        # so rwnd just advertises the receive buffer size
        ack = Segment(
            self.src_port, seg.src_port,
            seq_num=0, ack_num=self.expected_seq_num,
            flags=ACK, rwnd=self.receive_buffer_size
        )
        self._send_seg(ack, addr)

    def _log(self, seg):
        """
        Log a segment to the log file.
        """
        now = datetime.datetime.utcnow()
        ts = now.strftime('%Y-%m-%d %H:%M:%S') + f'.{now.microsecond // 1000:03d}'
        self.log_file.write(
            f"{ts} {seg.src_port} {seg.dst_port} "
            f"{seg.seq_num} {seg.ack_num} {seg.type_str()} "
            f"{seg.payload_length}\n"
        )
        self.log_file.flush()
