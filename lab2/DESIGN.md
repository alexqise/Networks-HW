# CSEE 4119 Spring 2026, Assignment 2 Design File
## Your name: Alex Qi


The MRT protocol is a simplified TCP built on top of UDP. It handles reliable, in-order delivery using a Go-Back-N sliding window, checksums for corruption detection, and flow control so the sender doesn't overwhelm the receiver.

Every segment has a 20-byte header packed in big-endian (`!HHIIBBHHH`) followed by an optional payload. The header fields are: src_port (2B), dst_port (2B), seq_num (4B), ack_num (4B), flags (1B), reserved (1B), rwnd (2B), payload_length (2B), and checksum (2B).

The flags byte encodes what kind of segment it is — SYN (0x01) for connection setup, ACK (0x02) for acknowledgments, FIN (0x04) for teardown, and DATA (0x08) for actual data. These get combined with bitwise OR, so a data segment with an ack is DATA|ACK (0x0A), and the server's handshake response is SYN|ACK (0x03).


Connection Set up: 
Standard 3-way handshake. Client sends SYN with seq=0, server responds with SYN|ACK and its rwnd, client sends ACK back. SYN consumes one sequence number so data starts at seq=1. If the SYN gets lost the client retransmits it after 0.5s. If the final ACK gets lost but the client starts sending data, the server treats the incoming DATA as an implicit ACK and moves to ESTABLISHED.

Data transfer uses Go-Back-N. The client fragments data into segments (max payload = segment_size - 20) and sends as many as the window allows. Window size is limited by the server's advertised rwnd.

The server only accepts in-order segments — if seq_num doesn't match what it expects, the segment is dropped. It always sends back a cumulative ACK with the next expected byte. When the client gets an ACK it slides the window forward. On timeout (0.5s) it retransmits the entire window from the base. Once everything is acked, send() returns.


Corruption:
Every segment has a 16-bit internet checksum (same algorithm as TCP). on send, the checksum field is zeroed, the whole segment is summed as 16-bit words with ones-complement arithmetic, and the inverted result becomes the checksum. On receive, the same process runs again — if the recomputed checksum doesn't match, the segment is silently dropped. From the protocol's perspective this looks the same as a lost packet.


Out of order handling:
The GBN receiver only accepts segments matching expected_seq_num. Anything out of order gets discarded and the server re-sends its last cumulative ACK. Eventually the client times out and retransmits from the window base, which fixes the ordering.


Flow control:
The server advertises its receive buffer size in the rwnd field of every ACK. The client caps unacked bytes in flight to peer_rwnd so it can't overwhelm the server.


Control teardown:
Client sends FIN, server responds with FIN|ACK, client sends final ACK. FIN consumes one seq number like SYN. If the FIN or FIN|ACK gets lost the client retransmits on timeout. The server has a 3-second timeout in FIN_RCVD so it doesn't hang forever waiting for the final ACK.

# multithreading
The client has 2 threads — main thread for the API calls and a handler thread that continuously receives/sends/retransmits using a non-blocking socket. The server has 3 threads — main thread for API calls, a receive thread that reads from the socket into a queue, and a segment handler thread that processes segments from the queue and manages the state machine.

Client states: CLOSED -> CONNECTING -> ESTABLISHED -> FIN_SENT -> CLOSED

Server states: LISTEN -> SYN_RCVD -> ESTABLISHED -> FIN_RCVD -> CLOSED