# 
# Columbia University - CSEE 4119 Computer Networks
# Assignment 1 - Adaptive video streaming
#
# server.py - the server program for taking request from the client and 
#             send the requested file back to the client
#

import socket


class Server:
    def __init__(self, serverport):
        # take in listening port arg
        self.serverport = serverport
        # create socket
        self.serverSocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        # bind to port num
        self.serverSocket.bind(('', self.serverport))

        # begin listening
        self.serverSocket.listen(1)
        print(f"Server is ready to receive connections on port {self.serverport}")

    def start(self):
        while True:
            # creates connection socket
            connectionSocket, addr = self.serverSocket.accept()
            print(f"Connected by {addr}")

            # receive file name
            filename = connectionSocket.recv(1024).decode()
            print(f"Requesting file: {filename}")

            # open and send that file
            file = open(filename, 'rb')
            connectionSocket.sendall(file.read())
            file.close()
            connectionSocket.close()


if __name__ == '__main__':
    server_port = int(sys.argv[1])
    server = Server(server_port)
    server.start()