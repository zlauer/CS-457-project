
import socket
import json
import time

HOST = "127.0.0.1"
PORT = 5000

def send_test_message(sock, message):
    encoded = (json.dumps(message) + "\n").encode("utf-8")
    sock.sendall(encoded)

    response = sock.recv(4096)
    print("Server response:")
    print(response.decode("utf-8"))


with socket.create_connection((HOST, PORT)) as sock:

    # Test CONNECT
    connect_message = {
        "msg_type": "CONNECT",
        "player_id": None,
        "payload": {"player_name": "Test Player"},
        "timestamp": time.time()
    }

    send_test_message(sock, connect_message)
