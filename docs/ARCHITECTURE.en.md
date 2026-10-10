# Architecture

[简体中文](ARCHITECTURE.md) | English

## Layers

`app.py / main.py` initializes DPI and the application. `ui/` handles widgets, user confirmation and events. `backend/services/` coordinates file operations, editing, search and changes plans. `backend/domain/` and `backend/formats/` implement calibration semantics and A2L/HEX parsing.

The backend never imports Tk or the UI. Failures are returned as exceptions; the UI decides how to display them. Pure calculations remain functions, while data and service responsibilities use classes.

| Component | Responsibility |
| --- | --- |
| Parameter / Conversion | Metadata, types, byte order, ranges; raw/physical conversion and interpolation |
| Entry / Session | Expanded values, original/pending bytes; pairing, validation and patches |
| A2LBlockParser / A2L | Syntax tree and layout/conversion semantics |
| HexImage / Record | Lossless HEX parsing and rendering |
| SearchQuery | Case-insensitive substring/wildcard search |
| HexWriter | Source checks, temporary output, verification and replacement |
| ChangePlanCodec | Address-free JSON and atomic import validation |
| FileService / EditService | All disk I/O; apply/revert/undo transactions |
| TranslationService | UTF-8 resources, placeholder validation, safe external overrides; no Tk dependency |
| Editor | Owns the single Tk root and shared UI/session state |
| LayoutMixin / TableMixin | Responsive layout, selection, filtering and details |
| EditingMixin / FileActionsMixin | Dialogs and confirmations; delegate data changes to services |
| ShortcutMixin / LanguageMixin | Key dispatch, menus, preferences and state-preserving language changes |
| JobMixin | Worker-to-Tk queue; widgets are touched only on the main thread |

UI mixins share the Editor's session and widget tree; they are not standalone windows. Language switching rebuilds widgets without recreating Session or clearing pending values/history. Preferences share the existing shortcuts JSON, with one additional `language` field. Older files without that field default to Chinese.

## Editing and saving

1. FileService loads either side and recreates the paired Session.
2. Entry retains original HEX bytes; edits are held in `pending` only.
3. Batch operations validate all items before EditService applies the transaction.
4. Session.patch emits only changed bytes; HexImage updates affected characters/checksums.
5. HexWriter checks the source, writes and verifies a temporary output, then replaces the target.
6. Saving retains pending edits relative to the original input for review.

Vendor CRCs, signatures and Bootloader verification are outside the HEX record checksum scope. No software-only check establishes hardware safety.

## Maintenance

- Add backend rules and tests before connecting them to UI.
- UI must not directly read/write files or mutate Entry.pending; architecture tests enforce this.
- Keep worker data processing separate from Tk callbacks.
- Add text to both JSON catalogs and use a resource key, never embedded display copy.
- Keep the legacy plan format and shortcuts location compatible.
- Builds/tests must not require customer firmware. Run `tests/run.ps1`; `build.ps1` tests before packaging.
- See [I18N](I18N.en.md) for resource extension and EXE packaging.
