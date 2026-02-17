import unittest

from protocol import build_query, parse_key_value


class ProtocolTests(unittest.TestCase):
    def test_parse_key_value_basic(self) -> None:
        self.assertEqual(parse_key_value("opmode=off"), ("opmode", "off"))

    def test_parse_key_value_colon(self) -> None:
        self.assertEqual(parse_key_value("TEMP: 42"), ("temp", "42"))

    def test_parse_key_value_whitespace(self) -> None:
        self.assertEqual(parse_key_value("  Power =  12.5 "), ("power", "12.5"))

    def test_parse_key_value_invalid(self) -> None:
        self.assertIsNone(parse_key_value("not a kv pair"))

    def test_build_query(self) -> None:
        self.assertEqual(build_query("opmode"), "opmode?")
        self.assertEqual(build_query("opmode?"), "opmode?")


if __name__ == "__main__":
    unittest.main()
