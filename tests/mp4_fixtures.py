"""Build ISOBMFF bytes that look like a Pocket 4P take.

Mirrors OpenPocketCine ClipColorProfileTests.mp4 — ftyp + optional mdat pad +
moov/meta/{keys,ilst} with com.dji.camera.ColorGammaSxS.
"""

from __future__ import print_function

import struct


GAMMA_KEY = "com.dji.camera.ColorGammaSxS"


def u32(value):
    return struct.pack(">I", value)


def box(type_or_fourcc, payload):
    if isinstance(type_or_fourcc, int):
        type_bytes = u32(type_or_fourcc)
    else:
        type_bytes = type_or_fourcc.encode("ascii")
        if len(type_bytes) != 4:
            raise ValueError("fourcc must be 4 bytes, got %r" % (type_or_fourcc,))
    return u32(8 + len(payload)) + type_bytes + payload


def color_gamma_mp4(gamma, pad_mdat=0, pad_before_meta=0):
    name = GAMMA_KEY.encode("utf-8")
    keys_payload = b"\x00\x00\x00\x00" + u32(1)
    keys_payload += u32(8 + len(name)) + b"mdta" + name
    keys = box("keys", keys_payload)

    data_payload = u32(1) + u32(0) + gamma.encode("utf-8")
    data_box = box("data", data_payload)
    child = box(1, data_box)
    ilst = box("ilst", child)
    meta = box("meta", keys + ilst)
    moov = box("moov", (b"\x00" * pad_before_meta) + meta)

    chunks = [box("ftyp", b"isomisom")]
    if pad_mdat:
        chunks.append(box("mdat", b"\xab" * pad_mdat))
    chunks.append(moov)
    return b"".join(chunks)
