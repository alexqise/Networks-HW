# 
# Columbia University - CSEE 4119 Computer Networks
# Assignment 1 - Adaptive video streaming
#
# client.py - the client program for sending request to the server and play the received video chunks
#

import threading
from queue import Queue
from video_player import play_chunks
import sys
import socket
import time
import os
import xml.etree.ElementTree as ET


def recv_line(sock):
    """
    Receive bytes from the socket until a newline is found.

    Returns the decoded line with the newline stripped.
    """
    data = b""
    while b"\n" not in data:
        data += sock.recv(1)
    return data.decode().strip()


def recv_exact(sock, n):
    """
    Receive exactly n bytes from the socket.

    Loops until all n bytes have been read, since TCP may
    deliver data in arbitrary-sized pieces.
    """
    data = b""
    while len(data) < n:
        data += sock.recv(n - len(data))
    return data


def recv_response(sock):
    """
    Receive a response from the server.

    Reads a newline-terminated length string, then reads that many
    bytes of payload. Returns None if length is 0.
    """
    length = int(recv_line(sock))
    if length == 0:
        return None
    return recv_exact(sock, length)


def parse_manifest(manifestData):
    """
    Parse the MPD manifest XML and return video metadata.

    Returns a tuple of (duration, chunkDuration, numChunks, bitrates)
    where bitrates is sorted ascending.
    """
    root = ET.fromstring(manifestData)
    duration = float(root.attrib["mediaPresentationDuration"])
    chunkDuration = float(root.attrib["maxSegmentDuration"])
    numChunks = int(duration / chunkDuration)
    bitrates = sorted(int(r.attrib["bandwidth"]) for r in root.iter("Representation"))
    return duration, chunkDuration, numChunks, bitrates


def client(server_addr, server_port, video_name, alpha, chunks_queue):
    """
    Connect to the server, request the manifest and video chunks
    using adaptive bitrate streaming, and write throughput to log.txt.

    arguments:
    server_addr -- the address of the server
    server_port -- the port number of the server
    video_name -- the name of the video
    alpha -- the alpha value for exponentially-weighted moving average
    chunks_queue -- the queue for passing the path of the chunks to the video player
    """
    clientSocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    clientSocket.connect((server_addr, server_port))
    connectionStart = time.time()

    # request and receive manifest
    clientSocket.sendall(f"{video_name}/manifest.mpd\n".encode())
    manifestData = recv_response(clientSocket)

    if manifestData is None:
        print("video not found")
        clientSocket.close()
        return

    duration, chunkDuration, numChunks, bitrates = parse_manifest(manifestData)

    os.makedirs("tmp", exist_ok=True)
    logFile = open("log.txt", "w")
    avgTput = 0

    for i in range(numChunks):
        # pick bitrate: lowest for first chunk, then highest supported
        if i == 0:
            bitrate = bitrates[0]
        else:
            bitrate = bitrates[0]
            for b in bitrates:
                if avgTput >= 1.5 * b:
                    bitrate = b

        chunkname = f"{video_name}_{bitrate}_{i:05d}.m4s"

        # request and receive chunk
        tStart = time.time()
        clientSocket.sendall(f"{video_name}/chunks/{chunkname}\n".encode())
        chunkData = recv_response(clientSocket)
        tEnd = time.time()

        # compute throughput and EWMA
        dur = tEnd - tStart
        tput = (len(chunkData) * 8) / dur
        avgTput = tput if i == 0 else alpha * tput + (1 - alpha) * avgTput

        # save chunk to tmp
        chunkPath = f"tmp/chunk_{i}.m4s"
        with open(chunkPath, "wb") as f:
            f.write(chunkData)
        chunks_queue.put(chunkPath)

        # write log line
        time_elapsed = tStart - connectionStart
        logFile.write(f"{time_elapsed} {dur} {tput} {avgTput} {bitrate} {chunkname}\n")

    logFile.close()
    clientSocket.close()


# parse input arguments and pass to the client function
if __name__ == '__main__':
    server_addr = sys.argv[1]
    server_port = int(sys.argv[2])
    video_name = sys.argv[3]
    alpha = float(sys.argv[4])

    # init queue for passing the path of the chunks to the video player
    chunks_queue = Queue()
    # start the client thread with the input arguments
    client_thread = threading.Thread(target = client, args =(server_addr, server_port, video_name, alpha, chunks_queue))
    client_thread.start()
    # start the video player
    play_chunks(chunks_queue)
