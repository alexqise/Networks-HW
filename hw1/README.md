# CSEE 4119 Spring 2026, Assignment 1
## Alexander Qi

### How to Run

Run all three programs in order:

1. `python3 server.py <listen_port>`
2. `python3 network.py <network_port> <server_addr> <server_port> <bw_file> <latency>`
3. `python3 client.py <network_addr> <network_port> <name> <alpha>`

### Files

- server.py: TCP server that listens for file requests and sends back the requested manifest or video chunk with a length-prefixed response.
- client.py: TCP client that connects through the network simulator, requests the manifest, then streams video chunks using using an ABR algo. Outputs `log.txt` and saves chunks to `tmp/`.
- network.py: Provided network simulator that relays traffic between client and server while throttling bandwidth according to `bw.txt`.
- video_play.py: Provided video player that displays downloaded chunks using OpenCV.
- bw.txt: Bandwidth schedule file, each line is `<time>:<bandwidth_bps>`.

### Assumptions

- The video chunk data directory is located at `./data/<name>/chunks/` relative to `server.py`.
- The manifest file is at `./data/<name>/manifest.mpd`.
- The server handles one client connection at a time.
- Ports used should be in the range 49152-65535 and not already in use.
