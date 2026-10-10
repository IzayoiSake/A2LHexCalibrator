# A2L HEX Calibrator

[简体中文](README.md) | English

A general-purpose offline Windows calibration editor. It reads A2L descriptions and actual values from Intel HEX, then saves edited values to another HEX file. It is not tied to a specific project, variable prefix, chip family or fixed address.

## Download and run

Download `A2LHexCalibrator.exe` from [Releases](https://github.com/IzayoiSake/A2LHexCalibrator/releases). No Python installation is required. The executable is not commercially code-signed; Windows may show an unknown-publisher warning. This is not a vendor flashing tool.

1. Load a matching A2L and Intel HEX pair, in either order.
2. Inspect recognized calibration objects. Arrays are expanded using zero-based linear memory indices.
3. Search names and descriptions using case-insensitive substring matching and Python `fnmatch` wildcards: `*` matches any characters; `?` matches one character. `Mon*` finds `Device1_Mon_...`. Square brackets are literal array indices, not character classes or regex.
4. Double-click a row, or select rows and press Enter, to edit. Physical values are the default; raw storage input is also available. Integers accept decimal, `0x` hexadecimal and `true/false`; enums accept labels or values.
5. Check the actual stored value and bytes. FLOAT32 values are quantized to storage precision. Yellow rows differ from the original HEX.
6. Preview changes, revert selected rows or undo. Ctrl/Shift selects multiple rows; Ctrl+A selects all filtered rows. Batch edits are validated completely before applying.
7. Save as HEX. Existing output files may be overwritten after confirmation; the loaded source HEX is protected. Output is written to a temporary file, verified and then replaced.

Use Save/Load changes JSON to transfer edits by parameter name without storing addresses. This supports new A2L/HEX versions, subject to name, type, unit and value validation. Import is atomic and undoable.

Default shortcuts include Ctrl+F (search), Ctrl+Z (undo), Ctrl+S (save changes JSON) and Ctrl+Shift+S (save HEX). All actions are listed under Edit; customize keys under Settings → Shortcuts.

## Languages and text configuration

Choose **Language → English** or **简体中文**. The selection applies immediately and persists across restarts. Loaded files, search/filter state, selection, unsaved edits and undo history are retained. Switching is temporarily ignored while a file operation or another window is active.

UI strings are stored in UTF-8 JSON under `src/a2l_hex_calibrator/locales/`. Both languages are embedded in the executable. To customize wording, place the provided JSON files in a `locales/` directory next to the EXE and restart. Missing/invalid overrides fall back to built-in strings. Keep keys and placeholders such as `{p0}` unchanged. See [I18N maintenance](docs/I18N.en.md).

A2L descriptions and enum labels are displayed as supplied, not machine-translated. Low-level parser diagnostics retain their original wording. Native Windows dialog buttons may follow the operating system language.

## What remains unchanged in HEX

- The input HEX is never modified in place. Saving without edits is byte-identical.
- With edits, only affected data characters and corresponding Intel HEX record checksums change.
- Other records, ordering, address records, entry points, line lengths, newline styles, whitespace and trailing `0x1A` padding are retained.
- Parameters may span records. Identical duplicate addresses are patched consistently; conflicting data at duplicate addresses is rejected.
- Output is parsed and compared before writing, then verified by readback. Saving is rejected if the source changed after loading.
- Missing addresses are never treated as zero. RAM-to-Flash mirrors and address aliases are not guessed. Overlapping calibration objects cannot be edited.

**Intel HEX record checksums are not vendor firmware CRCs, digital signatures or Bootloader metadata. Those are NOT recalculated. Perform all device-specific checks before flashing. Successful export does not prove the firmware is safe or ready to flash. A2L ranges are not hardware safety limits.**

## Supported formats

| Area | Support |
| --- | --- |
| A2L objects | VALUE, VAL_BLK; simple direct AXIS_PTS; value regions of CURVE/MAP/multidimensional tables with explicit MATRIX_DIM or complete fixed axes |
| Types | Signed/unsigned 8/16/32/64-bit integers; IEEE Float32/Float64 |
| Byte order | MSB_LAST / MSB_FIRST from object or MOD_COMMON; missing byte order is not guessed |
| Arrays | MATRIX_DIM or NUMBER; up to 100,000 elements; linear indices, no surface editor |
| Conversions | IDENTICAL, LINEAR, RAT_FUNC with a unique inverse within the physical range, strictly monotonic TAB_INTP/TAB_NOINTP, COMPU_VTAB enums |
| Bit fields | Contiguous BIT_MASK on unsigned integers; other bits preserved |
| HEX | Intel HEX record types 00–05; length/checksum validation |
| A2L encoding | UTF-8, GB18030, CP1252 attempts; encrypted ciphertext unsupported |

This is not a complete ASAP2 implementation. Multi-MODULE files, external `/include`, dynamic/vendor-specific layouts, indirect addresses, embedded axis/length counts, nonzero ECU_ADDRESS_EXTENSION, ASCII objects, FORM conversions, interval text tables, nonmonotonic/ambiguous conversions and overlapping/read-only/missing-data calibrations are rejected or marked unavailable.

A simple value layout has one position-1 FNC_VALUES with DIRECT and ROW_DIR/COLUMN_DIR. A standalone axis uses position-1 AXIS_PTS_X with DIRECT and INDEX_INCR. Complex layouts are never silently treated as contiguous arrays. Address availability alone cannot establish A2L/HEX version compatibility. Unknown enums may be displayed numerically but cannot be written as undefined labels.

## Development and build

```powershell
mamba env create -p .conda-env -f environment.yml
conda activate ./.conda-env
python app.py
pwsh -File ./tests/run.ps1
pwsh -File ./build.ps1
```

If the shared package cache is not writable, set `$env:CONDA_PKGS_DIRS = "$env:LOCALAPPDATA/mamba/pkgs"` in the current shell. Optional editable installation: `python -m pip install -e .`, then `python -m a2l_hex_calibrator`.

Build output is `dist/A2LHexCalibrator.exe`. First startup may take longer due to one-file extraction. The `.spec` is regenerated by `build.ps1` and is ignored by Git. Translation JSON is included through package-data settings and PyInstaller collection.

- `backend/`: UI-independent domain, formats and application services.
- `ui/`: Tk windows, menus and events; no direct disk writes or pending-byte mutation.
- `locales/`: Chinese and English UI resources.
- `tests/`: synthetic fixtures, backend/GUI/architecture/i18n tests and EXE smoke test.
- [Architecture](docs/ARCHITECTURE.en.md), [translation guide](docs/I18N.en.md), [release notes](CHANGELOG.en.md).

Legacy `A2LHexEditor.changes` JSON and `%APPDATA%/A2LHexEditor/shortcuts.json` remain compatible. Virtual environments, build output, firmware examples, secrets and local backups are not versioned. If endpoint encryption is installed, ensure build tools read plaintext before committing or building.
