
"""
client.py

Terminal-based Battleship client.

Connects to server.py using TCP and newline-delimited JSON messages.

The client handles:
    - Player registration
    - Lobby waiting
    - Manual ship placement
    - Sending shots
    - Displaying board updates
    - Game results
"""

import argparse
import socket
import sys
from collections import deque

from protocol import (
    BOARD_SIZE,
    FLEET,
    make_message,
    encode_message,
    decode_message,
    parse_coordinate,
    format_coordinate,
    validate_fleet,
    render_board,
)


# ---------------------------------------------------------------------
# Server connection and message handling
# ---------------------------------------------------------------------

class MessageConnection:
    """
    Manage a TCP connection using newline-delimited JSON messages.

    TCP is a byte stream, so one recv() does not necessarily contain
    exactly one complete message. This class buffers incoming bytes
    and separates complete messages using newline delimiters.
    """

    def __init__(self, hostname, port):
        self.socket = socket.create_connection(
            (hostname, port)
        )

        self.input_buffer = b""
        self.pending_messages = deque()

    def send(self, message):
        """Encode and send one complete protocol message."""

        self.socket.sendall(
            encode_message(message)
        )

    def receive(self):
        """
        Return the next complete protocol message.

        If multiple messages arrive together, additional messages
        remain in pending_messages for later calls.
        """

        if self.pending_messages:
            return self.pending_messages.popleft()

        while b"\n" not in self.input_buffer:

            received_data = self.socket.recv(4096)

            if not received_data:
                raise ConnectionError(
                    "The server closed the connection."
                )

            self.input_buffer += received_data

        while b"\n" in self.input_buffer:

            raw_message, self.input_buffer = (
                self.input_buffer.split(b"\n", 1)
            )

            if not raw_message.strip():
                continue

            message = decode_message(raw_message)
            self.pending_messages.append(message)

        if not self.pending_messages:
            return self.receive()

        return self.pending_messages.popleft()

    def close(self):
        """Close the TCP connection."""

        self.socket.close()


# ---------------------------------------------------------------------
# General display helpers
# ---------------------------------------------------------------------

def print_separator():
    """Print a visual separator in the terminal."""

    print("-" * 55)


def print_error(message):
    """Display an error returned by the server."""

    print(f"\nERROR: {message}")


def display_message(message):
    """Display a server-provided informational message."""

    payload = message.get("payload", {})
    text = payload.get("message")

    if text:
        print(f"\n{text}")


# ---------------------------------------------------------------------
# Player registration and lobby
# ---------------------------------------------------------------------

def connect_player(connection, player_name):
    """
    Send CONNECT and wait for the server to assign a player ID.

    The server identifies players by their TCP connection and
    assigns the player ID itself.
    """

    connection.send(
        make_message(
            "CONNECT",
            payload={
                "player_name": player_name
            },
        )
    )

    player_id = None

    print("\nConnecting to the Battleship server...")

    while player_id is None:

        message = connection.receive()
        msg_type = message.get("msg_type")
        payload = message.get("payload", {})

        if msg_type == "LOBBY_WAIT":
            player_id = message.get("player_id")
            display_message(message)

        elif msg_type == "STATE_UPDATE":
            # The server may send a state update immediately after
            # the second player connects.
            player_id = message.get("player_id")

        elif msg_type == "ERROR":
            raise ConnectionError(
                payload.get("message", "Connection rejected.")
            )

        elif msg_type == "GAME_OVER":
            raise ConnectionError(
                "The game has already ended."
            )

    print(f"\nYou are Player {player_id}.")

    return player_id


def wait_for_ship_placement(connection):
    """
    Wait until the server reports that both players are connected.
    """

    print("\nWaiting for another player...")

    while True:

        message = connection.receive()
        msg_type = message.get("msg_type")
        payload = message.get("payload", {})

        if msg_type == "STATE_UPDATE":
            if payload.get("stage") == "placing_ships":
                print("\nBoth players are connected!")
                print("It's time to place your ships.")
                return

        elif msg_type == "LOBBY_WAIT":
            display_message(message)

        elif msg_type == "ERROR":
            print_error(
                payload.get("message", "Unknown server error.")
            )

        elif msg_type == "GAME_OVER":
            display_message(message)
            raise ConnectionError("The game ended before placement.")


# ---------------------------------------------------------------------
# Manual ship placement
# ---------------------------------------------------------------------

def prompt_ship_placement():
    """
    Ask the player to manually position all five ships.

    The player enters a starting coordinate and orientation for
    each ship. The complete fleet is validated before it is returned.
    """

    print_separator()
    print("SHIP PLACEMENT")
    print_separator()

    print("Place each ship using the following format:")
    print("  Starting coordinate: A1 through J10")
    print("  Orientation: H for horizontal, V for vertical")
    print("\nYour fleet:")

    for ship_name, length in FLEET.items():
        print(f"  {ship_name}: {length} spaces")

    while True:

        ship_list = []

        for ship_name, length in FLEET.items():

            print_separator()
            print(f"Placing {ship_name} ({length} spaces)")

            while True:

                start = input(
                    f"Starting coordinate for {ship_name}: "
                ).strip().upper()

                try:
                    parse_coordinate(start)
                    break

                except ValueError as error:
                    print(f"Invalid coordinate: {error}")

            while True:

                orientation = input(
                    "Orientation (H/V): "
                ).strip().upper()

                if orientation in ("H", "V"):
                    break

                print("Please enter H or V.")

            ship_list.append(
                {
                    "name": ship_name,
                    "start": start,
                    "orientation": orientation,
                }
            )

        # Validate the entire fleet, including overlap and boundaries.
        valid, error_text, placements = validate_fleet(ship_list)

        if valid:
            print("\nYour fleet is valid!")
            return ship_list

        print(f"\nInvalid fleet: {error_text}")
        print("Let's enter your placements again.")


def place_ships(connection):
    """
    Submit the complete fleet to the server.

    If the server rejects the fleet, allow the player to correct it.
    """

    while True:

        ship_list = prompt_ship_placement()

        connection.send(
            make_message(
                "PLACE_SHIPS",
                payload={
                    "ships": ship_list
                },
            )
        )

        print("\nSubmitting your fleet to the server...")

        while True:

            message = connection.receive()
            msg_type = message.get("msg_type")
            payload = message.get("payload", {})

            if msg_type == "ERROR":
                print_error(
                    payload.get("message", "Fleet rejected.")
                )
                print("Please correct your placements.")
                break

            if msg_type == "STATE_UPDATE":

                stage = payload.get("stage")

                if stage == "waiting_for_opponent":
                    print(
                        "\nYour fleet was accepted! "
                        "Waiting for your opponent..."
                    )
                    return

                if stage == "playing":
                    return

            if msg_type == "GAME_OVER":
                display_message(message)
                raise ConnectionError(
                    "The game ended during ship placement."
                )


def wait_for_game_start(connection):
    """
    Wait for the server to start the game.

    The server starts only after both fleets have been accepted.
    """

    print("\nWaiting for both fleets to be accepted...")

    while True:

        message = connection.receive()
        msg_type = message.get("msg_type")
        payload = message.get("payload", {})

        if msg_type == "GAME_START":
            print_separator()
            print("BATTLESHIPS!")
            print_separator()
            display_message(message)
            return

        elif msg_type == "ERROR":
            print_error(
                payload.get("message", "Unknown server error.")
            )

        elif msg_type == "GAME_OVER":
            display_game_over(payload)
            return


# ---------------------------------------------------------------------
# Board display
# ---------------------------------------------------------------------

def convert_cells(cell_list):
    """Convert JSON [row, column] lists into Python tuples."""

    return {
        (cell[0], cell[1])
        for cell in cell_list
    }


def display_boards(payload):
    """Display the player's own board and opponent tracking board."""

    your_board = payload.get("your_board", {})
    opponent_board = payload.get("opponent_board", {})

    own_ships = convert_cells(
        your_board.get("ships", [])
    )

    incoming_hits = convert_cells(
        your_board.get("hits", [])
    )

    incoming_misses = convert_cells(
        your_board.get("misses", [])
    )

    outgoing_hits = convert_cells(
        opponent_board.get("hits", [])
    )

    outgoing_misses = convert_cells(
        opponent_board.get("misses", [])
    )

    print_separator()
    print("YOUR BOARD")
    print("S = Your ship | X = Your ship hit | o = Incoming miss")

    print(
        render_board(
            ship_cells=own_ships,
            hit_cells=incoming_hits,
            miss_cells=incoming_misses,
            reveal_ships=True,
        )
    )

    print_separator()
    print("OPPONENT'S BOARD")
    print("X = Your hit | o = Your miss | ~ = Unknown")

    print(
        render_board(
            hit_cells=outgoing_hits,
            miss_cells=outgoing_misses,
            reveal_ships=False,
        )
    )

    print_separator()


def display_last_move(payload):
    """Display the most recent shot result."""

    last_move = payload.get("last_move")

    if not last_move:
        return

    coordinate = last_move.get("coordinate")
    result = last_move.get("result")
    player_id = last_move.get("player_id")
    sunk_ship = last_move.get("sunk_ship")

    if result == "HIT":
        print(
            f"Player {player_id} hit at {coordinate}!"
        )

        if sunk_ship:
            print(f"They sank your {sunk_ship}!")

    elif result == "MISS":
        print(
            f"Player {player_id} missed at {coordinate}."
        )


def display_state(payload):
    """Display the boards and current turn information."""

    display_last_move(payload)
    display_boards(payload)

    active_player = payload.get("active_player")

    if active_player is not None:
        print(f"It is Player {active_player}'s turn.")


# ---------------------------------------------------------------------
# Taking a turn
# ---------------------------------------------------------------------

def prompt_shot():
    """
    Ask the player for a coordinate to fire at.

    Returns zero-based row and column values.
    """

    while True:

        coordinate = input(
            "\nEnter a coordinate to fire at (A1-J10), "
            "or Q to quit: "
        ).strip().upper()

        if coordinate == "Q":
            return None

        try:
            row, column = parse_coordinate(coordinate)
            return row, column

        except ValueError as error:
            print(f"Invalid coordinate: {error}")


def take_turn(connection):
    """
    Prompt the player for a shot and send MOVE.

    The server checks whether the shot is valid and whether it is
    the player's turn.
    """

    shot = prompt_shot()

    if shot is None:
        return False

    row, column = shot

    connection.send(
        make_message(
            "MOVE",
            payload={
                "row": row,
                "col": column,
            },
        )
    )

    return True


# ---------------------------------------------------------------------
# Game result handling
# ---------------------------------------------------------------------

def display_game_over(payload):
    """Display the winner and the reason the game ended."""

    print_separator()
    print("GAME OVER")
    print_separator()

    winner_name = payload.get("winner_name", "Unknown")
    winner_id = payload.get("winner_id")
    reason = payload.get("reason", "")

    print(f"Winner: {winner_name} (Player {winner_id})")

    if reason:
        print(reason)

    print_separator()


# ---------------------------------------------------------------------
# Main game loop
# ---------------------------------------------------------------------

def run_game(connection, player_id):
    """
    Process state updates and let the player take turns.

    The client waits for STATE_UPDATE messages from the server.
    It only prompts for a shot when the server identifies this
    player's ID as the active player.
    """

    print("\nThe game is ready!")

    while True:

        message = connection.receive()
        msg_type = message.get("msg_type")
        payload = message.get("payload", {})

        if msg_type == "GAME_OVER":
            display_game_over(payload)
            return

        if msg_type == "ERROR":
            print_error(
                payload.get("message", "Unknown server error.")
            )
            continue

        if msg_type != "STATE_UPDATE":
            continue

        if payload.get("stage") == "game_over":
            continue

        display_state(payload)

        active_player = payload.get("active_player")

        # It is not this client's turn, so wait for another update.
        if active_player != player_id:
            continue

        print("\nYour turn!")

        # Keep prompting if the server rejects a shot.
        # A valid shot will cause the server to send a new state.
        while True:

            shot = prompt_shot()

            if shot is None:
                return

            row, column = shot

            connection.send(
                make_message(
                    "MOVE",
                    payload={
                        "row": row,
                        "col": column,
                    },
                )
            )

            response = connection.receive()
            response_type = response.get("msg_type")
            response_payload = response.get("payload", {})

            if response_type == "ERROR":
                print_error(
                    response_payload.get(
                        "message",
                        "The server rejected your move.",
                    )
                )

                # The turn was not changed, so prompt again.
                continue

            if response_type == "GAME_OVER":
                display_game_over(response_payload)
                return

            if response_type == "STATE_UPDATE":
                # Save the new state for the next outer iteration.
                # The MessageConnection queue handles any messages
                # that arrived after this one.
                connection.pending_messages.appendleft(response)
                break


# ---------------------------------------------------------------------
# Command-line entry point
# ---------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Battleship terminal client."
    )

    parser.add_argument(
        "-i",
        "--hostname",
        default="127.0.0.1",
        help="Server IP address (default: 127.0.0.1).",
    )

    parser.add_argument(
        "-p",
        "--port",
        type=int,
        default=5000,
        help="Server port (default: 5000).",
    )

    args = parser.parse_args()

    if not 1 <= args.port <= 65535:
        parser.error("Port must be between 1 and 65535.")

    player_name = input("Enter your player name: ").strip()

    if not player_name:
        player_name = "Player"

    connection = None

    try:
        connection = MessageConnection(
            args.hostname,
            args.port,
        )

        player_id = connect_player(
            connection,
            player_name,
        )

        wait_for_ship_placement(connection)

        place_ships(connection)

        wait_for_game_start(connection)

        run_game(
            connection,
            player_id,
        )

    except (ConnectionError, OSError) as error:
        print(f"\nConnection problem: {error}")

    except KeyboardInterrupt:
        print("\nLeaving the game...")

    finally:
        if connection is not None:

            try:
                connection.send(
                    make_message("DISCONNECT")
                )
            except OSError:
                pass

            connection.close()

        print("Client disconnected.")


if __name__ == "__main__":
    main()
