"""Read-only sample integration checks. Patched firmware exists only in a temp dir."""

import hashlib
import json
import sys
import tempfile
from pathlib import Path
from a2l_hex_calibrator import A2L, HexImage, Session


def verify(directory):
    root = Path(directory)
    a2l_path = next(root.glob("*.a2l"))
    a2l = A2L.load(a2l_path)
    report = {"a2l": a2l_path.name, "objects": len(a2l.parameters), "files": []}
    for path in root.glob("*.hex"):
        content = path.read_bytes()
        image = HexImage(content)
        session = Session(a2l, image)
        assert image.render({})[0] == content
        chosen = []
        for kind in ["float", "integer", "array"]:
            for e in session.entries:
                if e.error or e.original is None or e.parameter.readonly or e in chosen:
                    continue
                match = (
                    (
                        kind == "float"
                        and e.parameter.dtype == "FLOAT32_IEEE"
                        and e.parameter.count == 1
                    )
                    or (
                        kind == "integer"
                        and e.parameter.dtype == "UBYTE"
                        and e.parameter.count == 1
                    )
                    or (kind == "array" and e.parameter.count > 1)
                )
                if not match:
                    continue
                raw = e.raw()
                for candidate in [0 if raw else 1, raw + 1]:
                    try:
                        session.set_value(e, str(candidate), raw_mode=True)
                    except ValueError:
                        continue
                    if e.changed:
                        chosen.append(e)
                        break
                if e in chosen:
                    break
        assert len(chosen) == 3, "Need scalar float, integer and array coverage"
        patch = session.patch()
        output, affected = image.render(patch)
        allowed = set()
        offsets = []
        cursor = 0
        for line in image.lines:
            offsets.append(cursor)
            cursor += len(line)
        for rec in image.records:
            changed = False
            for i, old in enumerate(rec.data):
                if rec.address + i in patch:
                    pos = offsets[rec.line] + rec.offset + 9 + 2 * i
                    allowed.update((pos, pos + 1))
                    changed = True
            if changed:
                pos = offsets[rec.line] + rec.offset + 9 + 2 * len(rec.data)
                allowed.update((pos, pos + 1))
        assert len(content) == len(output)
        differences = {i for i, (a, b) in enumerate(zip(content, output)) if a != b}
        assert differences <= allowed, "Unrelated text changed"
        with tempfile.TemporaryDirectory(prefix="a2l_hex_verify_") as tmp:
            target = Path(tmp) / "验证.hex"
            session.save_new(target, path)
            restored = Session(a2l, HexImage(target.read_bytes()))
            by_name = {e.name: e for e in restored.entries}
            for e in chosen:
                assert by_name[e.name].original == e.pending
        assert path.read_bytes() == content
        report["files"].append(
            {
                "name": path.name,
                "elements": len(session.entries),
                "readable": sum(not e.error and e.original is not None for e in session.entries),
                "unavailable": [
                    {"name": e.name, "reason": e.error} for e in session.entries if e.error
                ],
                "changed_test_items": [e.name for e in chosen],
                "changed_records": affected,
                "unrelated_bytes_unchanged": True,
                "source_unchanged": True,
                "sha256": hashlib.sha256(content).hexdigest(),
            }
        )
    return report


if __name__ == "__main__":
    result = verify(sys.argv[1])
    if len(sys.argv) > 2:
        Path(sys.argv[2]).write_text(
            json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
        )
    print(json.dumps(result, ensure_ascii=True, indent=2))
