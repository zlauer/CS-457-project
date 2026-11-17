
import json
import time


# ---------------------------------------------------------------------
# Game configuration
# ---------------------------------------------------------------------

BOARD_SIZE = 10

FLEET = {
    "Carrier": 5,
    "Battleship": 4,
    "Cruiser": 3,
    "Submarine": 3,
    "Destroyer": 2
}

MESSAGE_TYPES = {
    "CONNECT",
    "LOBBY_WAIT",
    "GAME_START",
    "PLACE_SHIPS",
    "MOVE",
    "STATE_UPDATE",
    "ERROR",
    "DISCONNECT",
    "GAME_OVER"
}


# ---------------------------------------------------------------------
# Message creation and encoding
# ---------------------------------------------------------------------

def make_message(msg_type, player_id=None, payload=None):
    if msg_type not in MESSAGE_TYPES:
        raise ValueError("Unknown message type.")

    return {
        "msg_type": msg_type,
        "player_id": player_id,
        "payload": payload if payload is not None else {},
        "timestamp": time.time()
    }


def encode_message(message):
    return (json.dumps(message) + "\n").encode("utf-8")


def decode_message(message_data):
    if isinstance(message_data, bytes):
        message_data = message_data.decode("utf-8")

    message = json.loads(message_data)

    if not isinstance(message, dict):
        raise ValueError("Message must be a JSON object.")

    if message.get("msg_type") not in MESSAGE_TYPES:
        raise ValueError("Message has an unknown or missing msg_type.")

    return message


# ---------------------------------------------------------------------
# Coordinate conversion
# ---------------------------------------------------------------------

def parse_coordinate(coordinate):
    if not isinstance(coordinate, str):
        raise ValueError("Coordinate must be a string.")

    coordinate = coordinate.strip().upper()

    if len(coordinate) < 2 or len(coordinate) > 3:
        raise ValueError("Coordinate must look like A1 through J10.")

    column_letter = coordinate[0]
    row_number = coordinate[1:]

    if column_letter < "A" or column_letter > "J":
        raise ValueError("Column must be between A and J.")

    if not row_number.isdigit():
        raise ValueError("Row must be a number.")

    row = int(row_number) - 1
    column = ord(column_letter) - ord("A")

    if row < 0 or row >= BOARD_SIZE:
        raise ValueError("Row must be between 1 and 10.")

    return row, column


def format_coordinate(row, column):
    if not (0 <= row < BOARD_SIZE and 0 <= column < BOARD_SIZE):
        raise ValueError("Coordinates are outside the board.")

    column_letter = chr(ord("A") + column)
    return f"{column_letter}{row + 1}"


# ---------------------------------------------------------------------
# Ship placement calculations
# ---------------------------------------------------------------------

def ship_coordinates(start, orientation, length):
    row, column = parse_coordinate(start)
    orientation = orientation.upper()

    if orientation == "H":
        cells = [
            (row, column + offset)
            for offset in range(length)
        ]

    elif orientation == "V":
        cells = [
            (row + offset, column)
            for offset in range(length)
        ]

    else:
        raise ValueError("Orientation must be H or V.")

    for cell_row, cell_column in cells:
        if not (
            0 <= cell_row < BOARD_SIZE
            and 0 <= cell_column < BOARD_SIZE
        ):
            raise ValueError("Ship placement extends outside the board.")

    return cells


# ---------------------------------------------------------------------
# Fleet validation
# ---------------------------------------------------------------------

def validate_fleet(ship_list):
    if not isinstance(ship_list, list):
        return False, "Ship placements must be provided as a list.", {}

    if len(ship_list) != len(FLEET):
        return False, "You must place all five ships.", {}

    placements = {}
    occupied_cells = set()

    for ship in ship_list:
        if not isinstance(ship, dict):
            return False, "Each ship placement must be an object.", {}

        name = ship.get("name")
        start = ship.get("start")
        orientation = ship.get("orientation")

        if name not in FLEET:
            return False, f"Unknown ship: {name}.", {}

        if name in placements:
            return False, f"{name} has been placed more than once.", {}

        if not isinstance(start, str):
            return False, f"{name} has an invalid starting coordinate.", {}

        if not isinstance(orientation, str):
            return False, f"{name} has an invalid orientation.", {}

        try:
            cells = ship_coordinates(
                start,
                orientation,
                FLEET[name]
            )
        except ValueError as error:
            return False, str(error), {}

        for cell in cells:
            if cell in occupied_cells:
                return False, f"{name} overlaps another ship.", {}

        placements[name] = cells
        occupied_cells.update(cells)

    if set(placements.keys()) != set(FLEET.keys()):
        return False, "The fleet is missing one or more ships.", {}

    return True, None, placements


# ---------------------------------------------------------------------
# Board rendering
# ---------------------------------------------------------------------

def render_board(
    ship_cells=None,
    hit_cells=None,
    miss_cells=None,
    reveal_ships=True
):
    """Build and return a printable 10x10 Battleship board."""

    # Start with every cell marked as unknown.
    board = [["~" for _ in range(BOARD_SIZE)]
             for _ in range(BOARD_SIZE)]

    # Only reveal ships on the player's own board.
    if reveal_ships:
        for row, column in ship_cells or []:
            board[row][column] = "S"

    # Show successful shots.
    for row, column in hit_cells or []:
        board[row][column] = "X"

    # Show missed shots.
    for row, column in miss_cells or []:
        board[row][column] = "o"

    # Build the board as text so the client can print it.
    lines = ["   A B C D E F G H I J"]

    for row_index, row in enumerate(board):
        lines.append(
            f"{row_index + 1:2} " + " ".join(row)
        )

    return "\n".join(lines)
