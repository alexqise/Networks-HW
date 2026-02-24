# 
# Columbia University - CSEE 4119 Computer Networks
# Assignment 1 - Adaptive video streaming
#
# server.py - the server program for taking request from the client and 
#             send the requested file back to the client
#

import socket

serverport = 60000

serverSocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

# bind to port num
serverSocket.bind(('', serverport))

# server begins listening for incoming TCP requests
serverSocket.listen(1)
print("Server is ready to receive connections")

while True:
    # server waits on accept() for incoming requests, new socket created on return
    connectionSocket, addr = serverSocket.accept()
    print(f"Connected by {addr}")

    # read bytes from connection
    filename = connectionSocket.recv(1024).decode()
    print(f"Requesting file: {filename}")

    # open the file name that has been requested
    file = open(filename, 'rb')

    # send it over
    connectionSocket.sendall(file.read())

    # close
    file.close()
    connectionSocket.close()