# 
# Columbia University - CSEE 4119 Computer Networks
# Assignment 1 - Adaptive video streaming
#
# server.py - the server program for taking request from the client and 
#             send the requested file back to the client
#

import socket
import sys
import os


class Server:
    def __init__(self, serverport):
        """
        Initialize the server and bind to the given port.

        arguments:
        serverport -- port number to listen on
        """
        self.serverport = serverport
        self.serverSocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.serverSocket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.serverSocket.bind(('', self.serverport))
        self.serverSocket.listen(1)
        print(f"Server is ready to receive connections on port {self.serverport}")

    def start(self):
        """
        Accept a client connection and serve file requests in a loop.

        Requests are newline-terminated file paths. Responses are the file
        length as a newline-terminated string followed by the file data,
        or "0\n" if the file is not found.
        """
        connectionSocket, addr = self.serverSocket.accept()
        print(f"Connected by {addr}")

        while True:
            request = b""
            while b"\n" not in request:
                data = connectionSocket.recv(1024)
                if not data:
                    connectionSocket.close()
                    self.serverSocket.close()
                    return
                request += data

            filename = request.decode().strip()
            filepath = f"./data/{filename}"
            print(f"Requesting file: {filepath}")

            if os.path.isfile(filepath):
                with open(filepath, "rb") as f:
                    fileData = f.read()
                connectionSocket.sendall(f"{len(fileData)}\n".encode() + fileData)
            else:
                connectionSocket.sendall("0\n".encode())

        connectionSocket.close()
        self.serverSocket.close()


if __name__ == '__main__':
    server_port = int(sys.argv[1])
    server = Server(server_port)
    server.start()
