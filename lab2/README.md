# CSEE 4119 Spring 2026, Assignment 2
## Your name: Alex Qi

## How to run

You need three terminals. Start them in this order:

```bash
# start the server
python app_server.py <server_port> <buffer_size>

# start the network simulator
python network.py <network_port> <client_addr> <client_port> <server_addr> <server_port> <loss_file>

# start the client
python app_client.py <client_port> <network_addr> <network_port> <segment_size>
```

The client reads data.txt and sends it to the server through the network simulator. The server receives 8000 bytes and compares them against the original file to make sure the transfer was correct.

## Files

- `mrt_client.py` - the client side of the MRT protocol. handles connecting to the server, fragmenting data into segments, sending them using a GBN sliding window, and closing the connection. runs a background handler thread for receiving ACKs and retransmitting on timeout.

- `mrt_server.py` - the server side. handles accepting connections, receiving data segments in order, sending back ACKs, and closing. uses two background threads: one for reading from the socket and one for processing segments.

- `mrt_segment.py` - defines the segment format (20-byte header + payload). has methods for packing segments into bytes, unpacking bytes back into segments, and verifying the internet checksum. also defines the flag constants (SYN, ACK, FIN, DATA).