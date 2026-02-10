# import Python's socket library
import socket

# define the server IP and port (i.e., our destination)
serverName = "10.207.57.70"
serverPort = 12000

# create a TCP socket, remote port 12000
clientSocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

# connect to server
clientSocket.connect((serverName, serverPort))

# get user input
message = input("Input lowercase sentence: ")

# send message into socket. No need to attach server name, port to message.
clientSocket.send(message.encode())

# read reply data (bytes) from socket
modifiedSentence = clientSocket.recv(1024)
print(modifiedSentence.decode())

# close socket
clientSocket.close()