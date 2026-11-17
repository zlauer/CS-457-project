
"""
server.py

Authoritative Battleship server.

Uses:
    - TCP sockets
    - selectors for non-blocking I/O
    - newline-delimited JSON messages
    - protocol.py for shared message and fleet validation

The server manages the lobby, ship placement, turns, shots,
board updates, wins, and disconnects.
"""

import argparse
import json
import selectors
import socket

from protocol import (
    BOARD_SIZE,
    FLEET,
    make_message,
    encode_message,
    decode_message,
    validate_fleet,
    format_coordinate,
)


# ---------------------------------------------------------------------
# Server configuration and game state
# ---------------------------------------------------------------------

HOST = "0.0.0.0"
DEFAULT_PORT = 5000

selector = selectors.DefaultSelector()

# Player information is stored by server-assigned player ID.
players = {}

game_started = False
game_over = False
active_player = None

# The most recent move is included in state updates so both clients
# can display what happened.
last_move = None


# ---------------------------------------------------------------------
# Socket output helpers
# ---------------------------------------------------------------------

def queue_message(client_socket, client_data, message):
    """
    Add a message to a client's output buffer.

    The message is not necessarily sent immediately. The selector
    will notify us when the socket is ready for writing.
    """

    encoded = encode_message(message)
    client_data["output_buffer"] += encoded

    try:
        selector.modify(
            client_socket,
            selectors.EVENT_READ | selectors.EVENT_WRITE,
            client_data,
        )
    except (KeyError, ValueError, OSError):
        # The client may already have disconnected.
        pass


def send_to_player(player_id, msg_type, payload=None):
    """Send a protocol message to one connected player."""

    player = players.get(player_id)

    if player is None:
        return

    message = make_message(
        msg_type,
        player_id=player_id,
        payload=payload,
    )

    queue_message(
        player["socket"],
        player,
        message,
    )


def broadcast_message(msg_type, payload=None):
    """Send the same message to every connected player."""

    for player_id in list(players):
        send_to_player(player_id, msg_type, payload)


# ---------------------------------------------------------------------
# Board and state helpers
# ---------------------------------------------------------------------

def serialize_cells(cells):
    """
    Convert a collection of (row, column) tuples into JSON-friendly
    lists of [row, column].
    """

    return [
        [row, column]
        for row, column in sorted(cells)
    ]


def get_player_board(player_id):
    """
    Build the player's own board information.

    This board can show their own ships and incoming shots.
    """

    player = players[player_id]

    ship_cells = set()

    for cells in player["fleet"].values():
        ship_cells.update(cells)

    opponent_id = 2 if player_id == 1 else 1
    opponent = players.get(opponent_id)

    incoming_hits = set()
    incoming_misses = set()

    if opponent is not None:
        incoming_hits = opponent["hits"]
        incoming_misses = opponent["shots"] - opponent["hits"]

    return {
        "ships": serialize_cells(ship_cells),
        "hits": serialize_cells(incoming_hits),
        "misses": serialize_cells(incoming_misses),
    }


def get_opponent_board(player_id):
    """
    Build the player's view of the opponent's board.

    IMPORTANT:
    This deliberately does not include the opponent's ship cells.
    Only the current player's own shots are visible.
    """

    player = players[player_id]

    return {
        "hits": serialize_cells(player["hits"]),
        "misses": serialize_cells(
            player["shots"] - player["hits"]
        ),
    }


def send_state_update():
    """
    Send a personalized state update to each connected player.

    Each player receives their own board and a hidden view of the
    opponent's board.
    """

    for player_id, player in list(players.items()):

        if not player["connected"]:
            continue

        if game_over:
            stage = "game_over"
        elif game_started:
            stage = "playing"
        elif len(players) == 2:
            if player["ready"]:
                stage = "waiting_for_opponent"
            else:
                stage = "placing_ships"
        else:
            stage = "waiting_for_players"

        payload = {
            "stage": stage,
            "active_player": active_player,
            "your_board": get_player_board(player_id),
            "opponent_board": get_opponent_board(player_id),
            "last_move": last_move,
        }

        opponent_id = 2 if player_id == 1 else 1
        opponent = players.get(opponent_id)

        payload["opponent_name"] = (
            opponent["name"] if opponent else None
        )

        send_to_player(
            player_id,
            "STATE_UPDATE",
            payload,
        )


# ---------------------------------------------------------------------
# Lobby and connection handling
# ---------------------------------------------------------------------

def handle_connect(client_socket, client_data, message):
    """
    Register a new player.

    The server assigns the player ID. It does not trust a player ID
    supplied by the client.
    """

    if client_data["player_id"] is not None:
        send_to_client_error(
            client_socket,
            client_data,
            "You are already registered.",
        )
        return

    if game_started or game_over or len(players) >= 2:
        send_to_client_error(
            client_socket,
            client_data,
            "The game is full or has already started.",
        )
        client_data["close_after_write"] = True
        return

    payload = message.get("payload", {})
    player_name = payload.get("player_name", "Player")

    if not isinstance(player_name, str):
        player_name = "Player"

    player_name = player_name.strip()[:20] or "Player"

    # Find the first available player slot.
    player_id = next(
        pid for pid in (1, 2)
        if pid not in players
    )

    client_data["player_id"] = player_id
    client_data["name"] = player_name
    client_data["fleet"] = {}
    client_data["shots"] = set()
    client_data["hits"] = set()
    client_data["ready"] = False
    client_data["connected"] = True

    players[player_id] = client_data

    print(
        f"{player_name} connected as Player {player_id}."
    )

    if len(players) == 1:
        send_to_player(
            player_id,
            "LOBBY_WAIT",
            {
                "message": "Waiting for another player."
            },
        )

    else:
        print("Both players connected. Ship placement can begin.")

        broadcast_message(
            "STATE_UPDATE",
            {
                "stage": "placing_ships",
                "message": "Both players connected. Place your ships.",
            },
        )

        # Send personalized state updates after the shared lobby notice.
        send_state_update()


def send_to_client_error(client_socket, client_data, error_text):
    """Send an ERROR message to a client, including an unregistered one."""

    player_id = client_data["player_id"]

    message = make_message(
        "ERROR",
        player_id=player_id,
        payload={"message": error_text},
    )

    queue_message(client_socket, client_data, message)


# ---------------------------------------------------------------------
# Ship placement
# ---------------------------------------------------------------------

def handle_place_ships(player_id, message):
    """
    Validate and save one complete fleet placement.

    The client sends all five ships in one PLACE_SHIPS message.
    The server independently validates the entire fleet.
    """

    player = players.get(player_id)

    if player is None:
        return

    if game_started:
        send_to_player(
            player_id,
            "ERROR",
            {"message": "Ship placement is already closed."},
        )
        return

    if player["ready"]:
        send_to_player(
            player_id,
            "ERROR",
            {"message": "Your fleet has already been accepted."},
        )
        return

    payload = message.get("payload", {})
    ship_list = payload.get("ships")

    valid, error_text, placements = validate_fleet(ship_list)

    if not valid:
        send_to_player(
            player_id,
            "ERROR",
            {"message": error_text},
        )
        return

    player["fleet"] = placements
    player["ready"] = True

    print(
        f"Player {player_id} ({player['name']}) "
        "has placed all five ships."
    )

    send_to_player(
        player_id,
        "STATE_UPDATE",
        {
            "stage": "waiting_for_opponent",
            "message": "Your fleet has been accepted. Waiting for the other player.",
        },
    )

    # The game begins only when both fleets have been accepted.
    if len(players) == 2 and all(
        player_data["ready"]
        for player_data in players.values()
    ):
        start_game()


def start_game():
    """Start the game after both players have valid fleets."""

    global game_started
    global active_player

    game_started = True
    active_player = 1

    print("Both fleets accepted. The game is starting.")

    for player_id in players:
        send_to_player(
            player_id,
            "GAME_START",
            {
                "message": "Both fleets are ready. The game has started.",
                "active_player": active_player,
            },
        )

    send_state_update()


# ---------------------------------------------------------------------
# Turn and shot handling
# ---------------------------------------------------------------------

def handle_move(player_id, message):
    """
    Process one shot.

    MOVE payload format:
        {
            "row": 0,
            "col": 0
        }

    Coordinates are zero-based integers.
    """

    global active_player
    global last_move

    player = players.get(player_id)

    if player is None:
        return

    if not game_started or game_over:
        send_to_player(
            player_id,
            "ERROR",
            {"message": "The game is not currently accepting moves."},
        )
        return

    if player_id != active_player:
        send_to_player(
            player_id,
            "ERROR",
            {"message": "It is not your turn."},
        )
        return

    opponent_id = 2 if player_id == 1 else 1
    opponent = players.get(opponent_id)

    if opponent is None:
        send_to_player(
            player_id,
            "ERROR",
            {"message": "Your opponent is no longer connected."},
        )
        return

    payload = message.get("payload", {})
    row = payload.get("row")
    column = payload.get("col")

    # bool is a subclass of int in Python, so reject it explicitly.
    if (
        isinstance(row, bool)
        or isinstance(column, bool)
        or not isinstance(row, int)
        or not isinstance(column, int)
    ):
        send_to_player(
            player_id,
            "ERROR",
            {"message": "MOVE requires integer row and col values."},
        )
        return

    if not (
        0 <= row < BOARD_SIZE
        and 0 <= column < BOARD_SIZE
    ):
        send_to_player(
            player_id,
            "ERROR",
            {"message": "That coordinate is outside the board."},
        )
        return

    target = (row, column)

    if target in player["shots"]:
        send_to_player(
            player_id,
            "ERROR",
            {"message": "You have already fired at that coordinate."},
        )
        return

    # Record the shot before resolving its result.
    player["shots"].add(target)

    opponent_ship_cells = set()

    for cells in opponent["fleet"].values():
        opponent_ship_cells.update(cells)

    if target in opponent_ship_cells:
        player["hits"].add(target)
        result = "HIT"
        print(
            f"Player {player_id} hit "
            f"{format_coordinate(row, column)}."
        )
    else:
        result = "MISS"
        print(
            f"Player {player_id} missed "
            f"{format_coordinate(row, column)}."
        )

    # Determine whether the shot sank a ship.
    sunk_ship = None

    if result == "HIT":
        for ship_name, cells in opponent["fleet"].items():
            if set(cells).issubset(player["hits"]):
                sunk_ship = ship_name
                break

    last_move = {
        "player_id": player_id,
        "coordinate": format_coordinate(row, column),
        "result": result,
        "sunk_ship": sunk_ship,
    }

    # Each valid shot changes the turn, whether it hits or misses.
    active_player = opponent_id

    # Five ships occupy 17 cells in total.
    total_ship_cells = sum(FLEET.values())

    if len(player["hits"]) == total_ship_cells:
        finish_game(
            winner_id=player_id,
            reason="All opponent ships have been sunk.",
        )
        return

    send_state_update()


# ---------------------------------------------------------------------
# Game completion
# ---------------------------------------------------------------------

def finish_game(winner_id, reason):
    """Declare a winner and notify both players."""

    global game_over
    global active_player

    if game_over:
        return

    game_over = True
    active_player = None

    winner = players.get(winner_id)

    if winner is None:
        return

    loser_id = 2 if winner_id == 1 else 1

    print(
        f"Player {winner_id} ({winner['name']}) wins! "
        f"{reason}"
    )

    for player_id in list(players):
        send_to_player(
            player_id,
            "GAME_OVER",
            {
                "winner_id": winner_id,
                "winner_name": winner["name"],
                "reason": reason,
            },
        )


# ---------------------------------------------------------------------
# Disconnect handling
# ---------------------------------------------------------------------

def close_client(client_socket, notify_opponent=True):
    """
    Unregister and close a client socket.

    If a player disconnects during an active game, the remaining
    player wins by forfeit.
    """

    global game_over
    global active_player

    try:
        client_data = selector.get_key(client_socket).data
    except KeyError:
        client_socket.close()
        return

    player_id = client_data["player_id"]

    try:
        selector.unregister(client_socket)
    except (KeyError, ValueError):
        pass

    client_socket.close()

    if player_id is None:
        return

    player = players.pop(player_id, None)

    if player is None:
        return

    player["connected"] = False

    print(
        f"{player['name']} (Player {player_id}) disconnected."
    )

    if not notify_opponent:
        return

    opponent_id = 2 if player_id == 1 else 1
    opponent = players.get(opponent_id)

    if opponent is None:
        return

    if game_started and not game_over:
        game_over = True
        active_player = None

        send_to_player(
            opponent_id,
            "GAME_OVER",
            {
                "winner_id": opponent_id,
                "winner_name": opponent["name"],
                "reason": "Your opponent disconnected. You win by forfeit.",
            },
        )

        print(
            f"Player {opponent_id} wins by forfeit."
        )

    else:
        send_to_player(
            opponent_id,
            "LOBBY_WAIT",
            {
                "message": "The other player disconnected. Waiting for another player."
            },
        )


# ---------------------------------------------------------------------
# Incoming message handling
# ---------------------------------------------------------------------

def process_message(client_socket, client_data, message):
    """Route a received protocol message to the correct handler."""

    if not isinstance(message, dict):
        send_to_client_error(
            client_socket,
            client_data,
            "Invalid message format.",
        )
        return

    msg_type = message.get("msg_type")
    player_id = client_data["player_id"]

    if msg_type == "CONNECT":
        handle_connect(
            client_socket,
            client_data,
            message,
        )

    elif msg_type == "DISCONNECT":
        close_client(client_socket)
        return

    elif player_id is None:
        send_to_client_error(
            client_socket,
            client_data,
            "Send CONNECT before sending game messages.",
        )

    elif msg_type == "PLACE_SHIPS":
        handle_place_ships(player_id, message)

    elif msg_type == "MOVE":
        handle_move(player_id, message)

    else:
        send_to_player(
            player_id,
            "ERROR",
            {"message": f"Message type {msg_type} is not valid here."},
        )


def read_client(client_socket, client_data):
    """
    Read incoming bytes and process complete newline-delimited messages.

    TCP does not preserve message boundaries. One recv() can contain
    part of a message, one message, or several messages. The input
    buffer handles all three cases.
    """

    try:
        received_data = client_socket.recv(4096)

    except BlockingIOError:
        return

    except OSError:
        close_client(client_socket)
        return

    if not received_data:
        close_client(client_socket)
        return

    client_data["input_buffer"] += received_data

    while b"\n" in client_data["input_buffer"]:

        raw_message, client_data["input_buffer"] = (
            client_data["input_buffer"].split(b"\n", 1)
        )

        if not raw_message.strip():
            continue

        try:
            message = decode_message(raw_message)

        except (UnicodeDecodeError, json.JSONDecodeError, ValueError):
            send_to_client_error(
                client_socket,
                client_data,
                "Could not decode the message.",
            )
            continue

        process_message(
            client_socket,
            client_data,
            message,
        )

        # A DISCONNECT message may have closed this socket.
        if client_socket not in selector.get_map():
            return

        if client_data["close_after_write"]:
            return


# ---------------------------------------------------------------------
# Outgoing message handling
# ---------------------------------------------------------------------

def write_client(client_socket, client_data):
    """Send as much buffered output as the socket will accept."""

    output_buffer = client_data["output_buffer"]

    if not output_buffer:
        return

    try:
        sent = client_socket.send(output_buffer)

    except BlockingIOError:
        return

    except OSError:
        close_client(client_socket)
        return

    client_data["output_buffer"] = output_buffer[sent:]

    if not client_data["output_buffer"]:

        if client_data["close_after_write"]:
            close_client(
                client_socket,
                notify_opponent=False,
            )
            return

        # No pending output remains, so we only need read events.
        try:
            selector.modify(
                client_socket,
                selectors.EVENT_READ,
                client_data,
            )
        except (KeyError, ValueError, OSError):
            close_client(client_socket)


# ---------------------------------------------------------------------
# Accept new connections
# ---------------------------------------------------------------------

def accept_connection(server_socket):
    """Accept a new TCP connection and register it with the selector."""

    try:
        client_socket, client_address = server_socket.accept()

    except BlockingIOError:
        return

    client_socket.setblocking(False)

    client_data = {
        "address": client_address,
        "player_id": None,
        "name": None,
        "input_buffer": b"",
        "output_buffer": b"",
        "fleet": {},
        "shots": set(),
        "hits": set(),
        "ready": False,
        "connected": True,
        "close_after_write": False,
    }

    selector.register(
        client_socket,
        selectors.EVENT_READ,
        client_data,
    )

    print(f"New connection from {client_address}.")


# ---------------------------------------------------------------------
# Main server loop
# ---------------------------------------------------------------------

def start_server(host, port):
    """Create the listening socket and run the selector event loop."""

    server_socket = socket.socket(
        socket.AF_INET,
        socket.SOCK_STREAM,
    )

    server_socket.setsockopt(
        socket.SOL_SOCKET,
        socket.SO_REUSEADDR,
        1,
    )

    server_socket.bind((host, port))
    server_socket.listen()
    server_socket.setblocking(False)

    selector.register(
        server_socket,
        selectors.EVENT_READ,
        data=None,
    )

    print(f"Battleship server listening on {host}:{port}")
    print("Waiting for two players...")

    try:
        while True:

            events = selector.select()

            for key, mask in events:

                current_socket = key.fileobj

                # The listening socket is ready to accept connections.
                if current_socket is server_socket:
                    accept_connection(server_socket)
                    continue

                client_data = key.data

                if mask & selectors.EVENT_READ:
                    read_client(
                        current_socket,
                        client_data,
                    )

                # A read event may have closed the socket.
                if current_socket not in selector.get_map():
                    continue

                if mask & selectors.EVENT_WRITE:
                    write_client(
                        current_socket,
                        client_data,
                    )

    except KeyboardInterrupt:
        print("\nServer shutting down.")

    finally:
        # Close every connected client.
        for client_socket in list(selector.get_map()):
            if client_socket is not server_socket:
                close_client(
                    client_socket,
                    notify_opponent=False,
                )

        selector.close()
        server_socket.close()


# ---------------------------------------------------------------------
# Command-line entry point
# ---------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Battleship game server."
    )

    parser.add_argument(
        "-i",
        "--hostname",
        default=HOST,
        help="IP address/interface to listen on (default: 0.0.0.0).",
    )

    parser.add_argument(
        "-p",
        "--port",
        type=int,
        default=DEFAULT_PORT,
        help=f"Port to listen on (default: {DEFAULT_PORT}).",
    )

    args = parser.parse_args()

    if not 1 <= args.port <= 65535:
        parser.error("Port must be between 1 and 65535.")

    start_server(
        args.hostname,
        args.port,
    )


if __name__ == "__main__":
    main()
