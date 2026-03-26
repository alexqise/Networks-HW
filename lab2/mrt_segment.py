import struct


# flag constants
SYN = 0x01
ACK = 0x02
FIN = 0x04
DATA = 0x08

# header format: big-endian
# src_port (H), dst_port (H), seq_num (I), ack_num (I), flags (B), reserved (B), rwnd (H), payload_length (H), checksum (H)
HEADER_FORMAT = '!HHIIBBHHH'
HEADER_SIZE = struct.calcsize(HEADER_FORMAT)  # 20 bytes


class Segment:
    """
    Represents a single MRT segment with a 20-byte header
    and variable-length payload.

    Header layout (20 bytes:
        offset  size  field
        0       2     src_port
        2       2     dst_port
        4       4     seq_num
        8       4     ack_num
        12      1     flags (SYN=0x01, ACK=0x02, FIN=0x04, DATA=0x08)
        13      1     reserved
        14      2     rwnd (receiver window in bytes)
        16      2     payload_length
        18      2     checksum (internet checksum)
        20+     var   payload
    """

    __slots__ = (
        'src_port', 'dst_port', 'seq_num', 'ack_num',
        'flags', 'rwnd', 'payload_length', 'checksum', 'payload'
    )

    def __init__(self, src_port, dst_port, seq_num, ack_num,
                 flags, rwnd, payload=b''):
        """
        Create a new segment with the given header fields and
        optional payload.

        arguments:
        src_port -- source port number
        dst_port -- destination port number
        seq_num -- sequence number (byte-stream offset)
        ack_num -- acknowledgment number (next expected byte)
        flags -- bitwise OR of flag constants (SYN, ACK, FIN, DATA)
        rwnd -- receiver window size in bytes
        payload -- application data bytes (default empty)
        """
        self.src_port = src_port
        self.dst_port = dst_port
        self.seq_num = seq_num
        self.ack_num = ack_num
        self.flags = flags
        self.rwnd = rwnd
        self.payload = payload
        self.payload_length = len(payload)
        self.checksum = 0

    def to_bytes(self):
        """
        Pack the segment into raw bytes for sending over UDP.
        Computes and embeds the internet checksum.

        return:
        bytes -- the packed segment (header + payload)
        """
        # first pack with checksum zeroed so we can compute it
        raw = struct.pack(
            HEADER_FORMAT,
            self.src_port, self.dst_port,
            self.seq_num, self.ack_num,
            self.flags, 0,
            self.rwnd, self.payload_length, 0
        ) + self.payload
        self.checksum = _compute_checksum(raw)
        # now pack again with the actual checksum
        raw = struct.pack(
            HEADER_FORMAT,
            self.src_port, self.dst_port,
            self.seq_num, self.ack_num,
            self.flags, 0,
            self.rwnd, self.payload_length, self.checksum
        ) + self.payload
        return raw

    @classmethod
    def from_bytes(cls, raw):
        """
        Unpack raw bytes into a Segment. Verifies the checksum
        and returns None if the segment is corrupted.

        arguments:
        raw -- the raw bytes received from the socket

        return:
        Segment or None -- the parsed segment, or None if corrupt
        """
        if len(raw) < HEADER_SIZE:
            return None

        (src_port, dst_port, seq_num, ack_num,
         flags, _pad, rwnd, payload_length, checksum) = struct.unpack(
            HEADER_FORMAT, raw[:HEADER_SIZE])

        # zero out the checksum field and recompute to verify
        raw_zeroed = raw[:18] + b'\x00\x00' + raw[20:]
        if _compute_checksum(raw_zeroed) != checksum:
            return None

        payload = raw[HEADER_SIZE:HEADER_SIZE + payload_length]

        # build segment without calling __init__
        seg = cls.__new__(cls)
        seg.src_port = src_port
        seg.dst_port = dst_port
        seg.seq_num = seq_num
        seg.ack_num = ack_num
        seg.flags = flags
        seg.rwnd = rwnd
        seg.payload_length = payload_length
        seg.checksum = checksum
        seg.payload = payload
        return seg

    def has_flag(self, flag):
        """
        Check if a specific flag bit is set.

        arguments:
        flag -- a flag constant (SYN, ACK, FIN, or DATA)

        return:
        bool -- True if the flag is set
        """
        return bool(self.flags & flag)

    def type_str(self):
        """
        Get a readable string for the segment type based on flags.
        Used for logging.

        return:
        str -- e.g. 'SYN', 'SYN|ACK', 'DATA|ACK', 'FIN', etc.
        """
        parts = []
        if self.flags & SYN:
            parts.append('SYN')
        if self.flags & ACK:
            parts.append('ACK')
        if self.flags & FIN:
            parts.append('FIN')
        if self.flags & DATA:
            parts.append('DATA')
        return '|'.join(parts) if parts else 'UNKNOWN'


def _compute_checksum(data):
    """
    Compute the internet checksum (ones-complement sum of 16-bit
    words) over the given bytes.

    arguments:
    data -- raw bytes to checksum

    return:
    int -- 16-bit checksum value
    """
    # pad to even length
    if len(data) % 2 == 1:
        data += b'\x00'
    total = 0
    for i in range(0, len(data), 2):
        word = (data[i] << 8) + data[i + 1]
        total += word
    # fold carry bits
    while total >> 16:
        total = (total & 0xFFFF) + (total >> 16)
    return ~total & 0xFFFF
