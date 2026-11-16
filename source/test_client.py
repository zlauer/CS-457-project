## generated to test a faux client interaction with server.py


import socket
import json

client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
client.connect(("127.0.0.1", 8080))

# Send CONNECT request
message = {
    "msg_type": "CONNECT",
    "payload": {
        "player_name": "Test Player"
    }
}

json_message = json.dumps(message).encode("utf-8") + b"\n"
client.sendall(json_message)

# Receive the server response
response = b""

while b"\n" not in response:
    data = client.recv(1024)

    if not data:
        break

    response += data

if response:
    received_message = json.loads(response.decode("utf-8").strip())
    print("Server response:", received_message)

client.close()
