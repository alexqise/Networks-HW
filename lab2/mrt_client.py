#
# Columbia University - CSEE 4119 Computer Networks
# Assignment 2 - Mini Reliable Transport Protocol
#
# mrt_client.py - defining client APIs of the mini reliable transport
# protocol
#

import socket # for UDP connection
import threading
import datetime

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

        # GBN sliding window state
        self.send_base = 0
        self.next_seq_num = 0
        self.send_end = 0
        self.seg_dict = {}  # seq_num -> payload bytes
        self.timer = Timer(timeout=0.5)

        # events for blocking calls
        self.connect_event = threading.Event()
        self.all_acked_event = threading.Event()
        self.close_event = threading.Event()

        # logging
        self.log_file = open(f"log_{src_port}.txt", "w")

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
        self._send_seg(syn)
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
        with self.lock:
            # if server already closed us, just clean up
            if self.state == 'CLOSED':
                self.running = False
                self.sock.close()
                self.log_file.close()
                return
            self.state = 'FIN_SENT'

        # send FIN, handler thread will retransmit on timeout
        fin = Segment(
            self.src_port, self.dst_port,
            seq_num=self.seq_num, ack_num=self.ack_num,
            flags=FIN, rwnd=0
        )
        self._send_seg(fin)
        self.timer.start()

        # block until teardown completes
        self.close_event.wait()
        self.running = False
        self.sock.close()
        self.log_file.close()

    def _send_seg(self, seg):
        """
        Send a segment over the socket and log it.
        """
        self.sock.sendto(seg.to_bytes(), (self.dst_addr, self.dst_port))
        self._log(seg)

    def _rcv_and_sgmnt_handler(self):
        """
        Handler thread that continuously receives and processes
        incoming segments. Handles handshake, data ACKs, sends
        new segments within the GBN window, and retransmits on
        timeout.
        """
        while self.running:
            # try to receive
            try:
                raw, addr = self.sock.recvfrom(65535)
                seg = Segment.from_bytes(raw)
                if seg is None:
                    continue  # corrupt, drop
                self._log(seg)
                self._handle_segment(seg)
            except (socket.timeout, BlockingIOError, OSError):
                pass

            # send data + check timeouts
            with self.lock:
                if self.state == 'CONNECTING':
                    self._check_syn_timeout()
                elif self.state == 'ESTABLISHED':
                    self._send_window()
                    self._check_data_timeout()
                elif self.state == 'FIN_SENT':
                    self._check_fin_timeout()

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
                    self._send_seg(ack)
                    self.state = 'ESTABLISHED'
                    self.timer.stop()
                    self.connect_event.set()

            elif self.state == 'ESTABLISHED':
                if seg.has_flag(FIN):
                    # server initiated close, send FIN-ACK
                    ack = Segment(
                        self.src_port, self.dst_port,
                        seq_num=self.seq_num, ack_num=seg.seq_num + 1,
                        flags=FIN | ACK, rwnd=0
                    )
                    self._send_seg(ack)
                    self.state = 'CLOSED'
                    self.timer.stop()
                    # unblock send() if it's waiting
                    self.all_acked_event.set()
                    self.close_event.set()
                elif seg.has_flag(ACK):
                    # update rwnd even if ack_num hasn't advanced
                    self.peer_rwnd = seg.rwnd
                    if seg.ack_num > self.send_base:
                        # cumulative ack, advance base
                        self.send_base = seg.ack_num
                        if self.send_base >= self.send_end:
                            # all data acked
                            self.timer.stop()
                            self.all_acked_event.set()
                        else:
                            # restart timer for remaining data
                            self.timer.reset()

            elif self.state == 'FIN_SENT':
                if seg.has_flag(FIN) and seg.has_flag(ACK):
                    # got FIN-ACK, send final ACK
                    ack = Segment(
                        self.src_port, self.dst_port,
                        seq_num=self.seq_num, ack_num=seg.seq_num + 1,
                        flags=ACK, rwnd=0
                    )
                    self._send_seg(ack)
                    self.state = 'CLOSED'
                    self.timer.stop()
                    self.close_event.set()
                elif seg.has_flag(FIN):
                    # server also trying to close (simultaneous close)
                    # send FIN-ACK back
                    ack = Segment(
                        self.src_port, self.dst_port,
                        seq_num=self.seq_num, ack_num=seg.seq_num + 1,
                        flags=FIN | ACK, rwnd=0
                    )
                    self._send_seg(ack)
                    self.state = 'CLOSED'
                    self.timer.stop()
                    self.close_event.set()

    def _send_window(self):
        """
        Send as many segments as the GBN window allows.
        Window is limited by peer_rwnd (flow control).
        """
        if self.send_base >= self.send_end:
            return

        while (self.next_seq_num < self.send_end
               and self.next_seq_num - self.send_base < self.peer_rwnd
               and self.next_seq_num in self.seg_dict):
            payload = self.seg_dict[self.next_seq_num]
            seg = Segment(
                self.src_port, self.dst_port,
                seq_num=self.next_seq_num, ack_num=self.ack_num,
                flags=DATA | ACK, rwnd=0, payload=payload
            )
            self._send_seg(seg)
            # start timer when first segment in window is sent
            if self.next_seq_num == self.send_base:
                self.timer.start()
            self.next_seq_num += len(payload)

    def _check_data_timeout(self):
        """
        GBN timeout: retransmit entire window from send_base.
        Also probes if rwnd is 0.
        """
        if not self.timer.is_expired() or self.send_base >= self.send_end:
            return

        if self.peer_rwnd == 0:
            # zero window probe: resend from base to get a fresh ACK
            # with updated rwnd
            if self.send_base in self.seg_dict:
                payload = self.seg_dict[self.send_base]
                seg = Segment(
                    self.src_port, self.dst_port,
                    seq_num=self.send_base, ack_num=self.ack_num,
                    flags=DATA | ACK, rwnd=0, payload=payload
                )
                self._send_seg(seg)
            self.timer.start()
        else:
            # reset next_seq_num to resend everything from base
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
            self._send_seg(syn)
            self.timer.start()

    def _check_fin_timeout(self):
        """
        Retransmit FIN if timeout expired during teardown.
        """
        if self.timer.is_expired():
            fin = Segment(
                self.src_port, self.dst_port,
                seq_num=self.seq_num, ack_num=self.ack_num,
                flags=FIN, rwnd=0
            )
            self._send_seg(fin)
            self.timer.start()

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
