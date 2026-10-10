"""合成 A2L/HEX 数据工厂；所有修改测试使用临时文件。"""

import struct
from a2l_hex_calibrator import A2L, HexImage, Session


def record(address, data=b"", kind=0, newline=b"\r\n"):
    raw = bytes([len(data)]) + address.to_bytes(2, "big") + bytes([kind]) + data
    return b":" + (raw + bytes([-sum(raw) & 255])).hex().upper().encode() + newline


def firmware(data, base=0x80000000, chunk=16):
    return (
        record(0, (base >> 16).to_bytes(2, "big"), 4)
        + b"".join(record(i, data[i : i + chunk]) for i in range(0, len(data), chunk))
        + record(0, b"\x80\x00\x00\x00", 5)
        + record(0, kind=1)
        + b"\x1a\x1a"
    )


def description(
    dtype="FLOAT32_IEEE",
    kind="VALUE",
    extra="",
    method="NO_COMPU_METHOD",
    defs="",
    order="MSB_LAST",
    limits="-1e30 1e30",
    address="0x80000000",
    name="Any_Project_Gain",
    layout=None,
):
    layout = layout or f"FNC_VALUES 1 {dtype} COLUMN_DIR DIRECT"
    return f"""ASAP2_VERSION 1 71
    /begin PROJECT Test "project"
      /begin MODULE Test "module"
        /begin MOD_COMMON "" BYTE_ORDER {order} /end MOD_COMMON
        /begin RECORD_LAYOUT Layout {layout} /end RECORD_LAYOUT
        {defs}
        /begin CHARACTERISTIC {name} "通用对象 / 中文描述" {kind} {address} Layout 0 {method} {limits}
            {extra}
        /end CHARACTERISTIC
      /end MODULE
    /end PROJECT"""


def session(text=None, data=None):
    return Session(
        A2L(text or description()),
        HexImage(firmware(data if data is not None else struct.pack("<f", 1.25))),
    )
