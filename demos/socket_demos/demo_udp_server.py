# import Python's socket library
import socket

# define port to bind this process to
serverPort = 12000

# create a UDP socket
serverSocket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

# bind socket to local port number
serverSocket.bind(("", serverPort))
print("Server ready to receive")

# loop forever
while True:

    # Read from UDP socket into message, getting client’s address (client IP and port)
    message, clientAddr = serverSocket.recvfrom(1024)
    print(clientAddr)

    # convert message to upper case
    modifiedMessage = message.decode().upper()

    # send uppercase message back to client
    serverSocket.sendto(modifiedMessage.encode(), clientAddr)
  