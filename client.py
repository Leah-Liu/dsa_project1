import socket

clientSocket = socket.socket()
host = socket.gethostname()
port = 8082
clientSocket.connect((host, port))
print(clientSocket.recv(1024))
clientSocket.close