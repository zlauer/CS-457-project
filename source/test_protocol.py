
import json
import unittest

from protocol import (
    parse_coordinate,
    format_coordinate,
    ship_coordinates,
    validate_fleet,
    make_message,
    encode_message,
    decode_message,
    validate_client_message,
)


# ---------------------------------------------------------------------
# Coordinate tests
# ---------------------------------------------------------------------

class TestCoordinates(unittest.TestCase):

    def test_valid_coordinates(self):
        self.assertEqual(parse_coordinate("A1"), (0, 0))
        self.assertEqual(parse_coordinate("C5"), (4, 2))
        self.assertEqual(parse_coordinate("J10"), (9, 9))

    def test_invalid_coordinates(self):
        invalid_coordinates = [
            "K1",
            "A11",
            "A0",
            "Z5",
            "A",
            "",
        ]

        for coordinate in invalid_coordinates:
            with self.subTest(coordinate=coordinate):
                with self.assertRaises(ValueError):
                    parse_coordinate(coordinate)

    def test_format_coordinate(self):
        self.assertEqual(format_coordinate(0, 0), "A1")
        self.assertEqual(format_coordinate(9, 9), "J10")

    def test_ship_coordinates(self):
        # Horizontal ship starting at B3.
        self.assertEqual(
            ship_coordinates("B3", "H", 4),
            [(2, 1), (2, 2), (2, 3), (2, 4)]
        )

        # Vertical ship starting at B3.
        self.assertEqual(
            ship_coordinates("B3", "V", 3),
            [(2, 1), (3, 1), (4, 1)]
        )

    def test_ship_out_of_bounds(self):
        with self.assertRaises(ValueError):
            ship_coordinates("J8", "H", 5)

    def test_invalid_ship_orientation_type(self):
        with self.assertRaises(ValueError):
            ship_coordinates("A1", 123, 5)

    def test_invalid_ship_orientation_value(self):
        with self.assertRaises(ValueError):
            ship_coordinates("A1", "D", 5)


# ---------------------------------------------------------------------
# Fleet validation tests
# ---------------------------------------------------------------------

class TestFleetValidation(unittest.TestCase):

    def setUp(self):
        self.valid_fleet = [
            {"name": "Carrier", "start": "A1", "orientation": "H"},
            {"name": "Battleship", "start": "C3", "orientation": "V"},
            {"name": "Cruiser", "start": "F2", "orientation": "H"},
            {"name": "Submarine", "start": "A5", "orientation": "V"},
            {"name": "Destroyer", "start": "H8", "orientation": "H"},
        ]

    def test_valid_fleet(self):
        valid, error, placements = validate_fleet(self.valid_fleet)

        self.assertTrue(valid)
        self.assertIsNone(error)
        self.assertEqual(len(placements), 5)

    def test_overlapping_ships(self):
        fleet = self.valid_fleet.copy()

        fleet[1] = {
            "name": "Battleship",
            "start": "A1",
            "orientation": "V",
        }

        valid, error, placements = validate_fleet(fleet)

        self.assertFalse(valid)
        self.assertIsNotNone(error)

    def test_missing_ship(self):
        fleet = self.valid_fleet[:-1]

        valid, error, placements = validate_fleet(fleet)

        self.assertFalse(valid)
        self.assertIsNotNone(error)

    def test_duplicate_ship(self):
        fleet = self.valid_fleet.copy()

        fleet[-1] = {
            "name": "Carrier",
            "start": "J1",
            "orientation": "H",
        }

        valid, error, placements = validate_fleet(fleet)

        self.assertFalse(valid)
        self.assertIsNotNone(error)

    def test_ship_out_of_bounds(self):
        fleet = self.valid_fleet.copy()

        fleet[0] = {
            "name": "Carrier",
            "start": "J8",
            "orientation": "H",
        }

        valid, error, placements = validate_fleet(fleet)

        self.assertFalse(valid)
        self.assertIsNotNone(error)

    def test_unknown_ship(self):
        fleet = self.valid_fleet.copy()

        fleet[0] = {
            "name": "Aircraft Carrier",
            "start": "A1",
            "orientation": "H",
        }

        valid, error, placements = validate_fleet(fleet)

        self.assertFalse(valid)
        self.assertIsNotNone(error)

    def test_invalid_fleet_type(self):
        valid, error, placements = validate_fleet("not a list")

        self.assertFalse(valid)
        self.assertIsNotNone(error)


# ---------------------------------------------------------------------
# Protocol message tests
# ---------------------------------------------------------------------

class TestMessages(unittest.TestCase):

    def test_make_message(self):
        message = make_message(
            "CONNECT",
            payload={"player_name": "Test Player"},
        )

        self.assertEqual(message["msg_type"], "CONNECT")
        self.assertIsNone(message["player_id"])

        self.assertEqual(
            message["payload"]["player_name"],
            "Test Player",
        )

        self.assertIn("timestamp", message)

    def test_encode_decode_message(self):
        original = make_message(
            "CONNECT",
            payload={"player_name": "Test Player"},
        )

        encoded = encode_message(original)

        self.assertTrue(encoded.endswith(b"\n"))

        decoded = decode_message(encoded.rstrip(b"\n"))

        self.assertEqual(
            decoded["msg_type"],
            original["msg_type"],
        )

        self.assertEqual(
            decoded["payload"],
            original["payload"],
        )

    def test_unknown_message_type(self):
        with self.assertRaises(ValueError):
            make_message("NOT_A_MESSAGE")

    def test_malformed_json(self):
        with self.assertRaises(json.JSONDecodeError):
            decode_message('{"msg_type": "CONNECT",')

    def test_missing_message_type(self):
        message = {
            "payload": {}
        }

        with self.assertRaises(ValueError):
            decode_message(json.dumps(message))

    def test_missing_payload(self):
        message = {
            "msg_type": "CONNECT"
        }

        with self.assertRaises(ValueError):
            decode_message(json.dumps(message))


# ---------------------------------------------------------------------
# Client message validation tests
# ---------------------------------------------------------------------

class TestClientMessageValidation(unittest.TestCase):

    def test_valid_connect_message(self):
        message = make_message(
            "CONNECT",
            payload={"player_name": "Test Player"},
        )

        valid, error = validate_client_message(message)

        self.assertTrue(valid)
        self.assertIsNone(error)

    def test_invalid_connect_message(self):
        message = make_message(
            "CONNECT",
            payload={"player_name": 123},
        )

        valid, error = validate_client_message(message)

        self.assertFalse(valid)
        self.assertIsNotNone(error)

    def test_invalid_move_payload(self):
        message = make_message(
            "MOVE",
            payload={"row": "A", "col": 5},
        )

        valid, error = validate_client_message(message)

        self.assertFalse(valid)
        self.assertIsNotNone(error)

    def test_move_boolean_coordinates(self):
        message = make_message(
            "MOVE",
            payload={"row": True, "col": 5},
        )

        valid, error = validate_client_message(message)

        self.assertFalse(valid)
        self.assertIsNotNone(error)

    def test_valid_move_message(self):
        message = make_message(
            "MOVE",
            payload={"row": 3, "col": 5},
        )

        valid, error = validate_client_message(message)

        self.assertTrue(valid)
        self.assertIsNone(error)

    def test_invalid_ship_payload(self):
        message = make_message(
            "PLACE_SHIPS",
            payload={"ships": "not a list"},
        )

        valid, error = validate_client_message(message)

        self.assertFalse(valid)
        self.assertIsNotNone(error)

    def test_missing_payload_in_client_message(self):
        message = {
            "msg_type": "CONNECT"
        }

        valid, error = validate_client_message(message)

        self.assertFalse(valid)
        self.assertIsNotNone(error)

    def test_reject_server_message_from_client(self):
        message = make_message(
            "GAME_START",
            payload={"active_player": 1},
        )

        valid, error = validate_client_message(message)

        self.assertFalse(valid)
        self.assertIsNotNone(error)

    def test_invalid_message_object(self):
        valid, error = validate_client_message("not a message")

        self.assertFalse(valid)
        self.assertIsNotNone(error)


# ---------------------------------------------------------------------
# Run tests
# ---------------------------------------------------------------------

if __name__ == "__main__":
    unittest.main()
