
"""
test_client.py

Automated two-player Battleship integration test.

Connects two independent TCP clients to server.py and tests:
    - Player registration
    - Fleet placement
    - Game startup
    - Wrong-turn rejection
    - Out-of-bounds move rejection
    - Hit and miss handling
    - Duplicate-shot rejection
    - Turn switching
    - Winning and game-over messages

Run server.py in one terminal first.
Then run this file in another terminal.
"""

import argparse
import socket
from collections import deque

from protocol import (
    BOARD_SIZE,
    FLEET,
    make_message,
    encode_message,
    decode_message,
    ship_coordinates,
)


# ---------------------------------------------------------------------
# Automated test configuration
# ---------------------------------------------------------------------

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 5000
DEFAULT_TIMEOUT = 10

tests_passed = 0


# ---------------------------------------------------------------------
# Automated test player
# ---------------------------------------------------------------------

class TestPlayer:
    """Represent one independent TCP client."""

    def __init__(self, name, hostname, port, timeout):
        self.name = name
        self.socket = socket.create_connection(
            (hostname, port),
            timeout=timeout,
        )

        self.socket.settimeout(timeout)

        self.input_buffer = b""
        self.pending_messages = deque()
        self.player_id = None

    def send(self, msg_type, payload=None):
        """Send one protocol message to the server."""

        message = make_message(
            msg_type,
            payload=payload,
        )

        self.socket.sendall(encode_message(message))

    def receive(self):
        """Receive one complete newline-delimited JSON message."""

        if self.pending_messages:
            return self.pending_messages.popleft()

        while b"\n" not in self.input_buffer:

            received_data = self.socket.recv(4096)

            if not received_data:
                raise ConnectionError(
                    f"{self.name}: Server closed the connection."
                )

            self.input_buffer += received_data

        while b"\n" in self.input_buffer:

            raw_message, self.input_buffer = (
                self.input_buffer.split(b"\n", 1)
            )

            if not raw_message.strip():
                continue

            self.pending_messages.append(
                decode_message(raw_message)
            )

        if not self.pending_messages:
            return self.receive()

        return self.pending_messages.popleft()

    def wait_for(self, expected_type):
        """Wait until the server sends a particular message type."""

        while True:

            message = self.receive()

            msg_type = message.get("msg_type")

            if msg_type == expected_type:
                return message

            if msg_type == "ERROR":
                raise AssertionError(
                    f"{self.name} received an unexpected error: "
                    f"{message.get('payload', {}).get('message')}"
                )

    def wait_for_stage(self, expected_stage):
        """Wait for a STATE_UPDATE with the requested game stage."""

        while True:

            message = self.receive()

            if message.get("msg_type") == "ERROR":
                raise AssertionError(
                    f"{self.name}: "
                    f"{message.get('payload', {}).get('message')}"
                )

            if message.get("msg_type") != "STATE_UPDATE":
                continue

            payload = message.get("payload", {})

            if payload.get("stage") == expected_stage:
                return message

    def expect_error(self, expected_text):
        """Verify that the server rejects an invalid request."""

        message = self.wait_for("ERROR")

        error_text = message.get("payload", {}).get("message", "")

        if expected_text.lower() not in error_text.lower():
            raise AssertionError(
                f"Expected error containing '{expected_text}', "
                f"but received '{error_text}'."
            )

    def close(self):
        """Close this simulated client."""

        self.socket.close()


# ---------------------------------------------------------------------
# Test reporting
# ---------------------------------------------------------------------

def report_pass(description):
    """Print a successful test result."""

    global tests_passed

    tests_passed += 1

    print(f"[PASS] {description}")


def send_move(player, row, column):
    """Send a MOVE message using zero-based coordinates."""

    player.send(
        "MOVE",
        {
            "row": row,
            "col": column,
        },
    )


def check_move_result(player, expected_result):
    """Verify the result of a successful move."""

    message = player.wait_for("STATE_UPDATE")

    payload = message.get("payload", {})
    last_move = payload.get("last_move", {})

    actual_result = last_move.get("result")

    if actual_result != expected_result:
        raise AssertionError(
            f"{player.name}: Expected {expected_result}, "
            f"received {actual_result}."
        )

    return payload


# ---------------------------------------------------------------------
# Test fleet construction
# ---------------------------------------------------------------------

def create_test_fleets():
    """
    Create two valid, non-overlapping fleets.

    Player 1 occupies alternating rows.
    Player 2 occupies the rows between them.

    This makes it possible to automatically generate
    guaranteed hits for Player 1 and guaranteed misses
    for Player 2.
    """

    player_one_fleet = [
        {"name": "Carrier", "start": "A1", "orientation": "H"},
        {"name": "Battleship", "start": "A3", "orientation": "H"},
        {"name": "Cruiser", "start": "A5", "orientation": "H"},
        {"name": "Submarine", "start": "A7", "orientation": "H"},
        {"name": "Destroyer", "start": "A9", "orientation": "H"},
    ]

    player_two_fleet = [
        {"name": "Carrier", "start": "A2", "orientation": "H"},
        {"name": "Battleship", "start": "A4", "orientation": "H"},
        {"name": "Cruiser", "start": "A6", "orientation": "H"},
        {"name": "Submarine", "start": "A8", "orientation": "H"},
        {"name": "Destroyer", "start": "A10", "orientation": "H"},
    ]

    return player_one_fleet, player_two_fleet


def get_fleet_cells(ship_list):
    """Convert a fleet into a set of occupied board coordinates."""

    occupied = set()

    for ship in ship_list:

        cells = ship_coordinates(
            ship["start"],
            ship["orientation"],
            FLEET[ship["name"]],
        )

        occupied.update(cells)

    return occupied


def get_hit_targets(ship_list):
    """Return every occupied coordinate in an opponent's fleet."""

    targets = []

    for ship in ship_list:

        targets.extend(
            ship_coordinates(
                ship["start"],
                ship["orientation"],
                FLEET[ship["name"]],
            )
        )

    return targets


def get_miss_targets(ship_list):
    """Generate coordinates guaranteed not to hit the given fleet."""

    occupied = get_fleet_cells(ship_list)

    misses = []

    for row in range(BOARD_SIZE):
        for column in range(BOARD_SIZE):

            coordinate = (row, column)

            if coordinate not in occupied:
                misses.append(coordinate)

    return misses


# ---------------------------------------------------------------------
# Main integration test
# ---------------------------------------------------------------------

def run_tests(hostname, port, timeout):

    player_one = None
    player_two = None

    try:

        print("=" * 55)
        print("       BATTLESHIP AUTOMATED INTEGRATION TEST")
        print("=" * 55)

        # ---------------------------------------------------------
        # 1. Connect both players
        # ---------------------------------------------------------

        print("\nTEST 1: Player connections")

        player_one = TestPlayer(
            "Player One",
            hostname,
            port,
            timeout,
        )

        player_one.send(
            "CONNECT",
            {"player_name": "Test Player One"},
        )

        response = player_one.receive()
        player_one.player_id = response.get("player_id")

        if player_one.player_id != 1:
            raise AssertionError("First client was not assigned Player 1.")

        report_pass("Player 1 connected and registered")

        player_two = TestPlayer(
            "Player Two",
            hostname,
            port,
            timeout,
        )

        player_two.send(
            "CONNECT",
            {"player_name": "Test Player Two"},
        )

        response = player_two.receive()
        player_two.player_id = response.get("player_id")

        if player_two.player_id != 2:
            raise AssertionError("Second client was not assigned Player 2.")

        report_pass("Player 2 connected and registered")

        # ---------------------------------------------------------
        # 2. Wait for both players to enter ship placement
        # ---------------------------------------------------------

        print("\nTEST 2: Lobby and ship placement")

        player_one.wait_for_stage("placing_ships")
        player_two.wait_for_stage("placing_ships")

        report_pass("Both players received the placement notification")

        player_one_fleet, player_two_fleet = create_test_fleets()

        player_one.send(
            "PLACE_SHIPS",
            {"ships": player_one_fleet},
        )

        response = player_one.wait_for_stage(
            "waiting_for_opponent"
        )

        report_pass("Player 1 fleet accepted")

        player_two.send(
            "PLACE_SHIPS",
            {"ships": player_two_fleet},
        )

        report_pass("Player 2 fleet submitted")

        # ---------------------------------------------------------
        # 3. Verify that the game starts
        # ---------------------------------------------------------

        print("\nTEST 3: Game startup")

        player_one.wait_for("GAME_START")
        player_two.wait_for("GAME_START")

        player_one.wait_for_stage("playing")
        player_two.wait_for_stage("playing")

        report_pass("Both players received GAME_START")
        report_pass("Both players entered the playing stage")

        # ---------------------------------------------------------
        # Prepare automatic shots
        # ---------------------------------------------------------

        hit_targets = get_hit_targets(player_two_fleet)
        miss_targets = get_miss_targets(player_one_fleet)

        if len(hit_targets) != sum(FLEET.values()):
            raise AssertionError("Incorrect number of hit targets.")

        if len(miss_targets) < 16:
            raise AssertionError("Not enough miss targets.")

        # ---------------------------------------------------------
        # 4. Test turn enforcement
        # ---------------------------------------------------------

        print("\nTEST 4: Turn enforcement")

        # Player 1 starts, so Player 2 must be rejected.
        send_move(player_two, 9, 9)

        player_two.expect_error("not your turn")

        report_pass("Out-of-turn move rejected")

        # ---------------------------------------------------------
        # 5. Test a successful hit
        # ---------------------------------------------------------

        print("\nTEST 5: Hits and misses")

        first_hit = hit_targets[0]

        send_move(
            player_one,
            first_hit[0],
            first_hit[1],
        )

        payload_one = check_move_result(
            player_one,
            "HIT",
        )

        payload_two = player_two.wait_for("STATE_UPDATE").get(
            "payload", {}
        )

        if payload_one.get("active_player") != 2:
            raise AssertionError("Turn did not switch to Player 2.")

        report_pass("Player 1 successfully hit an opposing ship")
        report_pass("Turn switched to Player 2")

        # ---------------------------------------------------------
        # 6. Test out-of-bounds move rejection
        # ---------------------------------------------------------

        print("\nTEST 6: Invalid coordinates")

        send_move(player_two, 10, 0)

        player_two.expect_error("outside the board")

        report_pass("Out-of-bounds move rejected")

        # ---------------------------------------------------------
        # 7. Player 2 makes a guaranteed miss
        # ---------------------------------------------------------

        first_miss = miss_targets[0]

        send_move(
            player_two,
            first_miss[0],
            first_miss[1],
        )

        check_move_result(player_two, "MISS")
        player_one.wait_for("STATE_UPDATE")

        report_pass("Player 2 successfully missed")

        # ---------------------------------------------------------
        # 8. Test duplicate-shot rejection
        # ---------------------------------------------------------

        print("\nTEST 7: Duplicate shots")

        send_move(
            player_one,
            first_hit[0],
            first_hit[1],
        )

        player_one.expect_error("already fired")

        report_pass("Repeated shot rejected")

        # ---------------------------------------------------------
        # 9. Automatically finish the game
        # ---------------------------------------------------------

        print("\nTEST 8: Complete automated game")

        # Player 1 already hit the first target.
        # Continue hitting the remaining 16 ship cells.
        # Player 2 fires a guaranteed miss after each hit,
        # except after the final winning shot.

        for index in range(1, len(hit_targets)):

            row, column = hit_targets[index]

            send_move(player_one, row, column)

            if index == len(hit_targets) - 1:

                # The final hit should end the game.
                break

            check_move_result(player_one, "HIT")
            player_two.wait_for("STATE_UPDATE")

            # Player 2 takes its turn with a guaranteed miss.
            miss_row, miss_column = miss_targets[index]

            send_move(
                player_two,
                miss_row,
                miss_column,
            )

            check_move_result(player_two, "MISS")
            player_one.wait_for("STATE_UPDATE")

        # ---------------------------------------------------------
        # 10. Verify victory
        # ---------------------------------------------------------

        print("\nTEST 9: Victory condition")

        game_over_one = player_one.wait_for("GAME_OVER")
        game_over_two = player_two.wait_for("GAME_OVER")

        winner_one = game_over_one.get("payload", {}).get("winner_id")
        winner_two = game_over_two.get("payload", {}).get("winner_id")

        if winner_one != 1 or winner_two != 1:
            raise AssertionError(
                "The server did not correctly declare Player 1 the winner."
            )

        report_pass("Player 1 received the victory message")
        report_pass("Player 2 received the defeat message")
        report_pass("All opposing ship cells were successfully hit")

        # ---------------------------------------------------------
        # Final report
        # ---------------------------------------------------------

        print("\n" + "=" * 55)
        print("             TEST RESULTS")
        print("=" * 55)

        print(f"Tests passed: {tests_passed}")
        print("Integration test completed successfully!")

        print("=" * 55)

    finally:

        if player_one is not None:
            player_one.close()

        if player_two is not None:
            player_two.close()


# ---------------------------------------------------------------------
# Command-line entry point
# ---------------------------------------------------------------------

def main():

    parser = argparse.ArgumentParser(
        description="Automated two-player Battleship integration test."
    )

    parser.add_argument(
        "-i",
        "--hostname",
        default=DEFAULT_HOST,
        help="Server IP address (default: 127.0.0.1).",
    )

    parser.add_argument(
        "-p",
        "--port",
        type=int,
        default=DEFAULT_PORT,
        help="Server port (default: 5000).",
    )

    parser.add_argument(
        "-t",
        "--timeout",
        type=int,
        default=DEFAULT_TIMEOUT,
        help="Socket timeout in seconds (default: 10).",
    )

    args = parser.parse_args()

    if not 1 <= args.port <= 65535:
        parser.error("Port must be between 1 and 65535.")

    if args.timeout <= 0:
        parser.error("Timeout must be greater than zero.")

    try:
        run_tests(
            args.hostname,
            args.port,
            args.timeout,
        )

    except (OSError, ConnectionError, AssertionError, ValueError) as error:
        print("\n[FAIL] Integration test failed.")
        print(f"Reason: {error}")
        raise SystemExit(1)


if __name__ == "__main__":
    main()
