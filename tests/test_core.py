import hashlib
import struct
import tempfile
import unittest
from unittest.mock import patch
from pathlib import Path
from a2l_hex_calibrator import A2L, HexImage, Session, FormatError, search_matches


from tests.fixtures import record, firmware, description, session


class HexTests(unittest.TestCase):
    def test_no_change_is_byte_identical(self):
        content = b" \r\n" + firmware(bytes(range(100))).replace(b":", b"  :")
        self.assertEqual(HexImage(content).render({})[0], content)

    def test_single_change_keeps_unrelated_text(self):
        content = firmware(bytes(range(64)))
        out, n = HexImage(content).render({0x80000005: 222})
        self.assertEqual(n, 1)
        left, right = content.splitlines(keepends=True), out.splitlines(keepends=True)
        for i in range(len(left)):
            if i != 1:
                self.assertEqual(left[i], right[i])
        self.assertEqual(
            HexImage(out).read(0x80000000, 64), bytes(range(5)) + bytes([222]) + bytes(range(6, 64))
        )

    def test_cross_record_value(self):
        h = HexImage(firmware(bytes(12), chunk=3))
        payload = struct.pack("<d", 2.5)
        out, _ = h.render({0x80000002 + i: v for i, v in enumerate(payload)})
        self.assertEqual(HexImage(out).read(0x80000002, 8), payload)

    def test_bad_checksum(self):
        content = firmware(bytes(16)).replace(b":0200000480007A", b":0200000480007B")
        with self.assertRaises(FormatError):
            HexImage(content)

    def test_missing_eof(self):
        with self.assertRaises(FormatError):
            HexImage(record(0, b"abc"))

    def test_after_eof(self):
        with self.assertRaises(FormatError):
            HexImage(firmware(b"abc") + record(0, b"a"))

    def test_identical_duplicate_records_patched_both(self):
        content = record(0, b"1234") + record(0, b"1234") + record(0, kind=1)
        out, n = HexImage(content).render({1: 77})
        self.assertEqual(n, 2)
        self.assertEqual(HexImage(out).read(0, 4), b"1M34")

    def test_conflicting_duplicate(self):
        with self.assertRaises(FormatError):
            HexImage(record(0, b"a") + record(0, b"b") + record(0, kind=1))

    def test_gap_not_zero_filled(self):
        h = HexImage(record(0, b"a") + record(2, b"b") + record(0, kind=1))
        with self.assertRaises(FormatError):
            h.read(0, 3)
        with self.assertRaises(FormatError):
            h.render({1: 0})

    def test_segment_address_and_start_preserved(self):
        content = (
            record(0, b"\x12\x34", 2)
            + record(3, b"AB")
            + record(0, b"\x12\x34\x00\x03", 3)
            + record(0, kind=1)
        )
        out, _ = HexImage(content).render({0x12343: 67})
        self.assertEqual(HexImage(out).read(0x12343, 2), b"CB")
        self.assertEqual(out.splitlines()[2:], content.splitlines()[2:])

    def test_lf_lowercase_padding_preserved(self):
        content = firmware(bytes([170]) * 20).lower().replace(b"\r\n", b"\n")
        out, _ = HexImage(content).render({0x80000000: 187})
        self.assertIn(b"bb", out)
        self.assertTrue(out.endswith(b"\x1a\x1a"))
        self.assertNotIn(b"\r", out)


class CalibrationTests(unittest.TestCase):
    def test_float(self):
        s = session()
        e = s.entries[0]
        self.assertEqual(e.raw(), 1.25)
        s.set_value(e, "2.5")
        self.assertEqual(e.raw(), 2.5)
        self.assertTrue(e.changed)
        self.assertEqual(e.display(True), "1.25")
        s.set_value(e, "1.25")
        self.assertFalse(e.changed)

    def test_big_endian(self):
        s = session(description("UWORD", order="MSB_FIRST", limits="0 65535"), b"\x12\x34")
        self.assertEqual(s.entries[0].raw(), 0x1234)
        s.set_value(s.entries[0], "0xabcd")
        self.assertEqual(s.entries[0].pending, b"\xab\xcd")

    def test_signed(self):
        s = session(description("SWORD"), struct.pack("<h", -32))
        s.set_value(s.entries[0], "-32768")
        self.assertEqual(s.entries[0].raw(), -32768)
        with self.assertRaises(FormatError):
            s.set_value(s.entries[0], "-32769")

    def test_uint64_exact(self):
        s = session(
            description("A_UINT64", limits="0 18446744073709551615"), struct.pack("<Q", 2**63 + 123)
        )
        self.assertEqual(s.entries[0].raw(), 2**63 + 123)
        s.set_value(s.entries[0], str(2**64 - 1))
        self.assertEqual(s.entries[0].raw(), 2**64 - 1)

    def test_array_linear(self):
        s = session(
            description("UWORD", "VAL_BLK", "MATRIX_DIM 2 3 1"),
            struct.pack("<6H", 1, 2, 3, 4, 5, 6),
        )
        self.assertEqual(len(s.entries), 6)
        self.assertTrue(s.entries[5].name.endswith("[5]"))
        s.set_value(s.entries[4], "99")
        out, _ = s.image.render(s.patch())
        self.assertEqual(
            struct.unpack("<6H", HexImage(out).read(0x80000000, 12)), (1, 2, 3, 4, 99, 6)
        )

    def test_number_array(self):
        s = session(description("UBYTE", "VAL_BLK", "NUMBER 3"), b"abc")
        self.assertEqual(len(s.entries), 3)

    def test_linear(self):
        defs = (
            '/begin COMPU_METHOD Scale "" LINEAR "%6.2" "V" COEFFS_LINEAR 0.5 -10 /end COMPU_METHOD'
        )
        s = session(description("UWORD", method="Scale", defs=defs), struct.pack("<H", 100))
        self.assertEqual(float(s.entries[0].display()), 40)
        s.set_value(s.entries[0], "50")
        self.assertEqual(s.entries[0].raw(), 120)
        with self.assertRaises(FormatError):
            s.set_value(s.entries[0], "50.1")

    def test_rational_direction(self):
        defs = (
            '/begin COMPU_METHOD Scale "" RAT_FUNC "%6.2" "V" COEFFS 0 2 10 0 0 1 /end COMPU_METHOD'
        )
        s = session(description("UWORD", method="Scale", defs=defs), struct.pack("<H", 100))
        self.assertEqual(float(s.entries[0].display()), 45)
        s.set_value(s.entries[0], "50")
        self.assertEqual(s.entries[0].raw(), 110)

    def test_nonlinear_rational_unique_domain(self):
        defs = (
            '/begin COMPU_METHOD Scale "" RAT_FUNC "%6.2" "V" COEFFS 1 0 0 0 0 1 /end COMPU_METHOD'
        )
        s = session(
            description("UWORD", method="Scale", defs=defs, limits="0 100"), struct.pack("<H", 25)
        )
        self.assertEqual(float(s.entries[0].display()), 5)
        s.set_value(s.entries[0], "6")
        self.assertEqual(s.entries[0].raw(), 36)
        s2 = session(
            description("UWORD", method="Scale", defs=defs, limits="-100 100"),
            struct.pack("<H", 25),
        )
        self.assertTrue(s2.entries[0].error)

    def test_numeric_table(self):
        defs = """/begin COMPU_METHOD Scale "" TAB_INTP "%6.2" "V" COMPU_TAB_REF Table /end COMPU_METHOD
                /begin COMPU_TAB Table "" TAB_INTP 3 0 0 10 100 20 300 /end COMPU_TAB"""
        s = session(description("UWORD", method="Scale", defs=defs), struct.pack("<H", 15))
        self.assertEqual(float(s.entries[0].display()), 200)
        s.set_value(s.entries[0], "100")
        self.assertEqual(s.entries[0].raw(), 10)
        with self.assertRaises(FormatError):
            s.set_value(s.entries[0], "400")

    def test_verbal_table(self):
        defs = """/begin COMPU_METHOD Mode "" TAB_VERB "%s" "" COMPU_TAB_REF Table /end COMPU_METHOD
                /begin COMPU_VTAB Table "" TAB_VERB 2 0 "OFF" 1 "ON" /end COMPU_VTAB"""
        s = session(description("UBYTE", method="Mode", defs=defs), b"\0")
        s.set_value(s.entries[0], "ON")
        self.assertEqual(s.entries[0].display(), "ON")
        with self.assertRaises(FormatError):
            s.set_value(s.entries[0], "2")

    def test_bitmask_preserves_other_bits(self):
        s = session(description("UBYTE", extra="BIT_MASK 0x0C"), b"\xf3")
        s.set_value(s.entries[0], "2")
        self.assertEqual(s.entries[0].pending, b"\xfb")

    def test_readonly(self):
        s = session(description(extra="READ_ONLY"))
        with self.assertRaises(FormatError):
            s.set_value(s.entries[0], "2")

    def test_range_and_nan(self):
        s = session(description(limits="0 5"))
        for value in ["-1", "6", "nan", "inf", "1e1000"]:
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    s.set_value(s.entries[0], value)

    def test_unknown_layout_not_silently_decoded(self):
        s = session(
            description(layout="NO_AXIS_PTS_X 1 UBYTE FNC_VALUES 2 FLOAT32_IEEE COLUMN_DIR DIRECT")
        )
        self.assertTrue(s.entries[0].error)

    def test_missing_byteorder_blocked(self):
        s = session(description().replace("BYTE_ORDER MSB_LAST", ""))
        self.assertTrue(s.entries[0].error)

    def test_byteorder_override(self):
        s = session(description("UWORD", extra="BYTE_ORDER MSB_FIRST"), b"\x12\x34")
        self.assertEqual(s.entries[0].raw(), 0x1234)

    def test_address_missing_is_not_zero(self):
        s = session(description(address="0x70000000"))
        self.assertIsNone(s.entries[0].original)
        self.assertTrue(s.entries[0].error)

    def test_alias_writes_blocked(self):
        text = description()
        block = '/begin CHARACTERISTIC Alias "" VALUE 0x80000000 Layout 0 NO_COMPU_METHOD 0 100 /end CHARACTERISTIC'
        text = text.replace("/end MODULE", block + " /end MODULE")
        s = session(text)
        with self.assertRaises(FormatError):
            s.set_value(s.entries[0], "2")

    def test_curve_fixed_axis(self):
        extra = "/begin AXIS_DESCR FIX_AXIS NO_INPUT_QUANTITY NO_COMPU_METHOD 3 0 100 FIX_AXIS_PAR_DIST 0 1 3 /end AXIS_DESCR"
        s = session(description("UBYTE", kind="CURVE", extra=extra), bytes([1, 2, 3]))
        self.assertEqual(len(s.entries), 3)
        self.assertFalse(s.entries[0].error)

    def test_axis_pts(self):
        text = """/begin PROJECT Test "" /begin MODULE Test ""
            /begin MOD_COMMON "" BYTE_ORDER MSB_LAST /end MOD_COMMON
            /begin RECORD_LAYOUT Axis AXIS_PTS_X 1 UWORD INDEX_INCR DIRECT /end RECORD_LAYOUT
            /begin AXIS_PTS X "axis" 0x80000000 NO_INPUT_QUANTITY Axis 0 NO_COMPU_METHOD 3 0 100 /end AXIS_PTS
            /end MODULE /end PROJECT"""
        s = session(text, struct.pack("<3H", 1, 2, 3))
        self.assertEqual(len(s.entries), 3)
        s.set_value(s.entries[1], "4")
        self.assertEqual(s.entries[1].raw(), 4)

    def test_wildcards_unicode_literal_brackets(self):
        s = session(description("UBYTE", "VAL_BLK", "NUMBER 3"), b"abc")
        e = s.entries[0]
        for pattern in ["project", "*_Gain[0]", "Any_*", "*中文*", "Any_Project_Gai?[0]"]:
            with self.subTest(pattern=pattern):
                self.assertTrue(search_matches(e, pattern))
        self.assertFalse(search_matches(e, "*_Gain[1]"))


class SaveTests(unittest.TestCase):
    def test_overwrite_existing_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "source.hex"
            target = Path(tmp) / "existing.hex"
            s = session()
            source.write_bytes(s.image.content)
            target.write_bytes(b"previous output")
            s.set_value(s.entries[0], "7.5")
            s.save_new(target, source, overwrite=True)
            self.assertEqual(target.read_bytes(), s.image.render(s.patch())[0])
            self.assertEqual(source.read_bytes(), s.image.content)
            with self.assertRaises(FormatError):
                s.save_new(source, source, overwrite=True)

    def test_failed_replace_preserves_destination(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "existing.hex"
            target.write_bytes(b"previous output")
            with patch(
                "a2l_hex_calibrator.backend.services.hex_writer.os.replace",
                side_effect=PermissionError("locked"),
            ):
                with self.assertRaises(PermissionError):
                    session().save_new(target, overwrite=True)
            self.assertEqual(target.read_bytes(), b"previous output")
            self.assertEqual(list(Path(tmp).iterdir()), [target])

    def test_mon_wildcard_contains(self):
        entry = session(description(name="Device1_Mon_cfCmd")).entries[0]
        for pattern in ("Mon*", "mon*cmd", "MON?cf*", "*", "", "Mon"):
            with self.subTest(pattern=pattern):
                self.assertTrue(search_matches(entry, pattern))
        for pattern in ("Mon*Missing", "Mon??cf", "Mon[0]*"):
            with self.subTest(pattern=pattern):
                self.assertFalse(search_matches(entry, pattern))

    def test_save_readback_and_original(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "原始.hex"
            target = Path(tmp) / "新的.hex"
            source.write_bytes(firmware(struct.pack("<f", 1.25)))
            s = session()
            s.set_value(s.entries[0], "7.5")
            digest = hashlib.sha256(source.read_bytes()).hexdigest()
            info = s.save_new(target, source)
            self.assertEqual(info["changed_parameters"], 1)
            self.assertEqual(
                struct.unpack("<f", HexImage(target.read_bytes()).read(0x80000000, 4))[0], 7.5
            )
            self.assertEqual(hashlib.sha256(source.read_bytes()).hexdigest(), digest)
            with self.assertRaises(FormatError):
                s.save_new(source, source)
            with self.assertRaises(FormatError):
                s.save_new(target, source)

    def test_source_external_change_blocked(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "a.hex"
            source.write_bytes(b"changed")
            with self.assertRaises(FormatError):
                session().save_new(Path(tmp) / "b.hex", source)

    def test_zero_change_save_exact(self):
        with tempfile.TemporaryDirectory() as tmp:
            s = session()
            target = Path(tmp) / "copy.hex"
            s.save_new(target)
            self.assertEqual(target.read_bytes(), s.image.content)


if __name__ == "__main__":
    unittest.main(verbosity=2)
