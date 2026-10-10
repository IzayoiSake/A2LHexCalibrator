import json
import struct
import unittest
from a2l_hex_calibrator import A2L, HexImage, Session, FormatError
from tests.fixtures import description, firmware


class PlanTests(unittest.TestCase):
    def source(self):
        session = Session(A2L(description()), HexImage(firmware(struct.pack("<f", 1))))
        session.set_value(session.entries[0], "2.5")
        return session

    def test_cross_version_address_and_unchanged_excluded(self):
        source = self.source()
        text = source.export_changes()
        self.assertNotIn("address", text)
        target = Session(
            A2L(description(address="0x90000000")),
            HexImage(firmware(struct.pack("<f", 4), base=0x90000000)),
        )
        changes = target.import_changes(text)
        self.assertEqual(target.entries[0].raw(), 4)
        for entry, pending in changes:
            entry.pending = pending
        self.assertEqual(target.entries[0].raw(), 2.5)
        target.entries[0].pending = None
        self.assertEqual(json.loads(target.export_changes())["parameters"], {})

    def test_missing_name_is_atomic(self):
        source = self.source()
        data = json.loads(source.export_changes())
        data["parameters"]["Missing"] = {"value": "3", "mode": "physical", "unit": ""}
        with self.assertRaises(FormatError):
            source.import_changes(json.dumps(data))
        self.assertEqual(source.entries[0].raw(), 2.5)

    def test_invalid_value_and_unit(self):
        for field, value in [("value", "NaN"), ("unit", "wrong"), ("mode", "unknown")]:
            source = self.source()
            data = json.loads(source.export_changes())
            next(iter(data["parameters"].values()))[field] = value
            with self.assertRaises(ValueError):
                source.import_changes(json.dumps(data))

    def test_duplicate_json_key(self):
        with self.assertRaises(FormatError):
            self.source().import_changes('{"format": 1, "format": 2}')


if __name__ == "__main__":
    unittest.main()
