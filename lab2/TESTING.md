# CSEE 4119 Spring 2026, Assignment 2 Testing File
## Your name: Alex Qi

All tests run locally with the provided app_client.py, app_server.py, and network.py. Client sends data.txt (~8024 bytes) through the network simulator, server receives 8000 bytes and checks against the original. Ports: client=50000, network=51000, server=60000, segment_size=1460, buffer=4096.

- **No loss** (Loss.txt: `0 0.0 0.0`) — baseline test, everything works clean. handshake completes instantly, all 6 data segments go through, teardown finishes. PASS

- **10% packet loss** (Loss.txt: `0 0.1 0.0`) — some segments and ACKs get dropped, retransmissions kick in after 0.5s timeouts. takes a couple seconds but completes fine. PASS

- **Bit errors only** (Loss.txt: `0 0.0 0.001`) — 0.1% bit error rate means most segments get at least one flipped bit. checksum catches them all, they get dropped and retransmitted. PASS

- **10% loss + bit errors** (Loss.txt: `0 0.1 0.001`) — both loss and corruption at once. this is the toughest test since ACKs can also get corrupted. takes longer but still works. the FIN exchange sometimes needs a few retries. PASS

- **30% packet loss** (Loss.txt: `0 0.3 0.0`) — heavy loss, roughly half of round trips fail. lots of retransmissions but the GBN window still makes progress. PASS
