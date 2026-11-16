## generated test code for testing server.py
## to test: 
## python3 server.py -p 8080
##  listening for stuff and things...
## enter python3 test.py
## connection legitimacy

import socket

client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
client.connect(("127.0.0.1", 8080))

client.sendall(b"Hello server!")

client.close()