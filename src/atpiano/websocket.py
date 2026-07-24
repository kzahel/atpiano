"""Small RFC 6455 server framing used by the loopback-only workbench."""

from __future__ import annotations

import base64
import hashlib
import json
import struct
from dataclasses import dataclass
from typing import BinaryIO

WEBSOCKET_GUID = "258EAFA5-E914-47DA-95CA-C5AB0DC85B11"
MAX_WEBSOCKET_PAYLOAD_BYTES = 256 * 1024


@dataclass(frozen=True)
class WebSocketFrame:
    opcode: int
    payload: bytes


def websocket_accept(key: str) -> str:
    try:
        decoded = base64.b64decode(key, validate=True)
    except ValueError as error:
        raise ValueError("invalid WebSocket key") from error
    if len(decoded) != 16:
        raise ValueError("invalid WebSocket key")
    digest = hashlib.sha1((key + WEBSOCKET_GUID).encode("ascii")).digest()
    return base64.b64encode(digest).decode("ascii")


def read_frame(stream: BinaryIO) -> WebSocketFrame | None:
    prefix = stream.read(2)
    if not prefix:
        return None
    if len(prefix) != 2:
        raise ValueError("WebSocket frame ended in its prefix")
    first, second = prefix
    if not first & 0x80:
        raise ValueError("fragmented WebSocket messages are not supported")
    if first & 0x70:
        raise ValueError("WebSocket reserved bits are not supported")
    opcode = first & 0x0F
    masked = bool(second & 0x80)
    if not masked:
        raise ValueError("client WebSocket frames must be masked")
    payload_length = second & 0x7F
    if payload_length == 126:
        length_bytes = stream.read(2)
        if len(length_bytes) != 2:
            raise ValueError("WebSocket frame ended in its length")
        payload_length = struct.unpack("!H", length_bytes)[0]
    elif payload_length == 127:
        length_bytes = stream.read(8)
        if len(length_bytes) != 8:
            raise ValueError("WebSocket frame ended in its length")
        payload_length = struct.unpack("!Q", length_bytes)[0]
    if payload_length > MAX_WEBSOCKET_PAYLOAD_BYTES:
        raise ValueError("WebSocket frame exceeds the payload limit")
    mask = stream.read(4)
    if len(mask) != 4:
        raise ValueError("WebSocket frame ended in its mask")
    payload = stream.read(payload_length)
    if len(payload) != payload_length:
        raise ValueError("WebSocket frame ended in its payload")
    return WebSocketFrame(
        opcode=opcode,
        payload=bytes(value ^ mask[index % 4] for index, value in enumerate(payload)),
    )


def encode_frame(payload: bytes, *, opcode: int) -> bytes:
    first = 0x80 | opcode
    length = len(payload)
    if length < 126:
        prefix = bytes((first, length))
    elif length <= 0xFFFF:
        prefix = bytes((first, 126)) + struct.pack("!H", length)
    else:
        prefix = bytes((first, 127)) + struct.pack("!Q", length)
    return prefix + payload


def encode_json(value: dict[str, object]) -> bytes:
    payload = json.dumps(value, sort_keys=True, allow_nan=False).encode("utf-8")
    return encode_frame(payload, opcode=0x1)
