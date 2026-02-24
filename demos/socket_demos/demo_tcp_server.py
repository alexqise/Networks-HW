# import Python's socket library
import socket

# define port to bind this process to
serverPort = 12000

# create TCP welcoming socket
serverSocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

# bind welcoming socket to local port number
serverSocket.bind(("", serverPort))

# server begins listening for incoming TCP requests
serverSocket.listen(1)
print("Server is ready to receive connections")

# loop forever
while True:

    # server waits on accept() for incoming requests, new socket created on return
    connectionSocket, clientAddr = serverSocket.accept()

    # read bytes from socket (but not address as in UDP)
    message = connectionSocket.recv(1024).decode()
   
    # capitalize and send
    modifiedMessage = message.upper()
    connectionSocket.send(modifiedMessage.encode())
 
    # close connection to this client (but not welcoming socket)
    connectionSocket.close()
   