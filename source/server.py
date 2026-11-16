import argparse  ## assignment requirement!
# import sys
import socket
import selectors
import json

## commands:
## python3 server.py -h
## python3 server.py -p PORTp

#player assigning and recognition
players = {
    # this will not be populated until a player exists, however
    
}


# pulls up server_help.txt
with open("server_help.txt", "r") as file:
    help_text = file.read()

parser = argparse.ArgumentParser(
    description=help_text,
    formatter_class=argparse.RawDescriptionHelpFormatter
)

parser.add_argument(
    "-p",
    "--port",
    type=int,
    required=True,
    help="TCP port the server will listen on"
)

args = parser.parse_args()

# creation of a tcp socket, binding of the port, listening for connection, and setting to non-blocking
server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
server_socket.bind(("0.0.0.0", args.port))
server_socket.listen()
server_socket.setblocking(False)
selector = selectors.DefaultSelector()

# listening & open for a connection on the socket
selector.register(
    server_socket,
    selectors.EVENT_READ,
    data=None
)

# helper function - designed to queue outgoing messages
def queue_message(client_socket, client_data, message):

    # Convert dictionary into newline-delimited JSON bytes
    message_bytes = json.dumps(message).encode("utf-8") + b"\n"

    # Add message to the client's output buffer
    client_data["output_buffer"].extend(message_bytes)

    # Tell the selector this socket is ready to send data
    selector.modify(
        client_socket,
        selectors.EVENT_READ | selectors.EVENT_WRITE,
        data=client_data
    )

#event loop
            
while True:
    events = selector.select()

    for key, mask in events:
        if key.fileobj is server_socket:
            client_socket, client_address = server_socket.accept()

            # Set the new client socket to non-blocking
            client_socket.setblocking(False)

            # Register the client socket with the selector
            selector.register(
                client_socket,
                selectors.EVENT_READ,
                data={
                    "input_buffer": bytearray(),
                    "output_buffer": bytearray(),
                    "player_id": None
}
            )

            print(f"New connection from {client_address}")
            

        else:
            client_socket = key.fileobj
            client_data = key.data

            # HANDLE INCOMING MESSAGES
            if mask & selectors.EVENT_READ:

                try:
                    data = client_socket.recv(1024)
                except BlockingIOError:
                    data = None

                if data == b"":
                    print("Client disconnected.")

                    player_id = client_data["player_id"]

                    if player_id is not None:
                        players.pop(player_id, None)

                    selector.unregister(client_socket)
                    client_socket.close()
                    continue

                elif data is not None:

                    # Add incoming bytes to this client's buffer
                    input_buffer = client_data["input_buffer"]
                    input_buffer.extend(data)

                    # Process every complete message in the buffer
                    while b"\n" in input_buffer:
                        newline_index = input_buffer.index(b"\n")

                        raw_message = input_buffer[:newline_index]

                        # Remove the processed message and its newline
                        del input_buffer[:newline_index + 1]

                        try:
                            message = json.loads(raw_message.decode("utf-8"))

                            print("Received message:", message)

                            if not isinstance(message, dict):
                                print("Invalid message format.")

                            elif message.get("msg_type") == "CONNECT":

                                # Prevent the same connection from registering twice
                                if client_data["player_id"] is not None:
                                    print("This client is already registered.")

                                else:
                                    # Find an available player slot
                                    player_id = next(
                                        (pid for pid in (1, 2) if pid not in players),
                                        None
                                    )

                                    if player_id is None:
                                        print("Lobby is full.")

                                    else:
                                        # Register the player
                                        players[player_id] = client_socket
                                        client_data["player_id"] = player_id

                                        queue_message(
                                            client_socket,
                                            client_data,
                                            {
                                                "msg_type": "TEST_RESPONSE",
                                                "payload": {
                                                    "message": "Successfully connected to server!",
                                                    "player_id": player_id
                                                }
                                            }
                                        )

                                        print(f"Player {player_id} connected.")

                                        if len(players) == 1:
                                            print("Waiting for another player...")

                                        elif len(players) == 2:
                                            print("Both players connected!")

                        except (UnicodeDecodeError, json.JSONDecodeError):
                            print("Received an invalid JSON message.")

            # HANDLE OUTGOING MESSAGES
            if mask & selectors.EVENT_WRITE:

                output_buffer = client_data["output_buffer"]

                if output_buffer:

                    try:
                        sent = client_socket.send(output_buffer)
                    except BlockingIOError:
                        sent = 0

                    if sent > 0:
                        # Remove successfully transmitted bytes
                        del output_buffer[:sent]

                # Disable write monitoring when buffer is empty
                if not output_buffer:
                    selector.modify(
                        client_socket,
                        selectors.EVENT_READ,
                        data=client_data
                    )
