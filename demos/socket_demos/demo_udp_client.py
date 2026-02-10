# import Python's socket library
import socket

# define the server IP and port (i.e., our destination)
serverName = "10.207.57.70"
serverPort = 12000

# create a UDP socket
clientSocket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

# get user input
message = input("Input lowercase sentence: ")

# attach serve name, port to message; send into socket
clientSocket.sendto(message.encode(), (serverName, serverPort))

# read reply data (bytes) from socket
modifiedMessage, serverAddress = clientSocket.recvfrom(1024)

# print out received string and close socket
print(modifiedMessage.decode())

clientSocket.close()
print("Closed")
