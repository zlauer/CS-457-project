## generated to test a faux client interaction with server.py

import socket
import json

client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
client.connect(("127.0.0.1", 8080))

message = {
    "msg_type": "CONNECT",
    "payload": {
        "player_name": "Player 1"
    }
}

json_message = json.dumps(message).encode("utf-8") + b"\n"

print(json.dumps(message, indent=2))

client.sendall(json_message)

client.close()