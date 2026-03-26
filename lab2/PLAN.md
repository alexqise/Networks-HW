# MRT Protocol Implementation Plan

## Context
Assignment 2 for CSEE 4119: Build a Mini Reliable Transport (MRT) protocol on top of UDP. The protocol must handle segment loss, corruption, out-of-order delivery, high latency, segmentation, and flow control. A network simulator (`network.py`) sits between client and server, dropping packets and flipping bits per a loss configuration file.

## Files to Create/Modify
| File | Action |
|------|--------|
| `mrt_segment.py` | **Create** — Segment class (pack/unpack/checksum) |
| `mrt_client.py` | **Modify** — Full Client implementation |
| `mrt_server.py` | **Modify** — Full Server implementation |
| `Loss.txt` | **Create** — Loss configuration for testing |

## Segment Header (20 bytes, big-endian `!HHIIBBHHH`)

| Offset | Size | Field | Description |
|--------|------|-------|-------------|
| 0 | 2 | src_port | Source port |
| 2 | 2 | dst_port | Destination port |
| 4 | 4 | seq_num | Sequence number (byte-stream offset) |
| 8 | 4 | ack_num | Next expected byte |
| 12 | 1 | flags | SYN=0x01, ACK=0x02, FIN=0x04, DATA=0x08 |
| 13 | 1 | reserved | Padding (0x00) |
| 14 | 2 | rwnd | Receiver window (bytes) |
| 16 | 2 | payload_len | Payload length |
| 18 | 2 | checksum | Internet checksum (ones-complement) |
| 20+ | var | payload | Application data |

## Implementation Phases

### Phase 1: UDP Socket Setup
Establish basic UDP connection in `init()` for both client and server. Bind sockets, store addresses. Verify client can send a raw byte string to server through `network.py` (0% loss).

### Phase 2: Segment Class (`mrt_segment.py`)
Implement the `Segment` class with `to_bytes()` and `from_bytes()`. Test standalone: create a segment, pack it, unpack it, verify fields match. Flip a bit, verify checksum rejects it.

### Phase 3: Multithreading
Add the threading scaffolding (no protocol logic yet):
- **Client:** spawn `_rcv_and_sgmnt_handler` in `init()`, verify it can receive raw bytes from socket
- **Server:** spawn `_rcv_handler` and `_sgmnt_handler` in `init()`, verify segments flow through the Queue from rcv_handler → sgmnt_handler → data_buffer → `receive()`

### Phase 4: 3-Way Handshake
Implement `connect()` / `accept()` with SYN → SYN-ACK → ACK. Use state attributes to track CONNECTING/SYN_RCVD/ESTABLISHED. Test with 0% loss first.

### Phase 5: Basic Data Transfer
Send and receive application data using `Segment` class over the established connection. No sliding window yet — just send segments one at a time and verify data arrives correctly. Test with 0% loss.

### Phase 6: Timer Class
Implement a `Timer` utility class with convenience methods: `start()`, `stop()`, `is_expired()`, `reset()`. Both client and server instantiate this for timeout detection.

### Phase 7: Timeout Detection + Retransmission
Integrate the Timer with send/receive. Add losses via `Loss.txt` (e.g., `0 0.1 0.0`). Verify the client detects timeouts when segments are dropped and retransmits.

### Phase 8: Sliding Window (GBN) + ACKs + Flow Control
- Client: GBN sender with sliding window, cumulative ACK processing, retransmit-on-timeout
- Server: GBN receiver discards out-of-order, sends cumulative ACKs with `rwnd`
- Test with various loss rates and small buffer sizes

### Phase 9: Connection Teardown
Implement `close()` with FIN → FIN-ACK → ACK. Test end-to-end.

### Phase 10: Logging + Polish
Format log files per spec. Test under corruption (`0 0.1 0.001`).

### Phase 11: Documentation
Write README.md, DESIGN.md, TESTING.md.

## Testing Commands
```bash
# Terminal 1: Start server
python app_server.py 60000 4096

# Terminal 2: Start network simulator (0% loss)
python network.py 51000 127.0.0.1 50000 127.0.0.1 60000 Loss.txt

# Terminal 3: Start client
python app_client.py 50000 127.0.0.1 51000 1460
```
