import argparse  ## assignment requirement!
# import sys
import socket
import selectors

## commands:
## python3 server.py -h
## python3 server.py -p PORTp

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
                data=None
            )

            print(f"New connection from {client_address}")