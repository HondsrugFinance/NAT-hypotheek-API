"""
Minimale protobuf encoder/decoder voor Calcasa gRPC-Web calls.
Geen .proto bestanden nodig — handmatige wire-format encoding.
"""

import struct
import base64
from dataclasses import dataclass


# ─── Wire Types ───────────────────────────────────────────────
WIRE_VARINT = 0
WIRE_64BIT = 1
WIRE_LENGTH_DELIMITED = 2
WIRE_32BIT = 5


# ─── Encoder ──────────────────────────────────────────────────

def encode_varint(value: int) -> bytes:
    """Encode een unsigned integer als protobuf varint."""
    result = bytearray()
    while value > 0x7F:
        result.append((value & 0x7F) | 0x80)
        value >>= 7
    result.append(value & 0x7F)
    return bytes(result)


def encode_field_varint(field_number: int, value: int) -> bytes:
    """Encode field tag + varint value."""
    tag = encode_varint((field_number << 3) | WIRE_VARINT)
    return tag + encode_varint(value)


def encode_field_string(field_number: int, value: str) -> bytes:
    """Encode field tag + length-delimited string."""
    data = value.encode("utf-8")
    tag = encode_varint((field_number << 3) | WIRE_LENGTH_DELIMITED)
    return tag + encode_varint(len(data)) + data


def encode_field_bytes(field_number: int, value: bytes) -> bytes:
    """Encode field tag + length-delimited bytes (voor nested messages)."""
    tag = encode_varint((field_number << 3) | WIRE_LENGTH_DELIMITED)
    return tag + encode_varint(len(value)) + value


def encode_field_double(field_number: int, value: float) -> bytes:
    """Encode field tag + 64-bit double."""
    tag = encode_varint((field_number << 3) | WIRE_64BIT)
    return tag + struct.pack("<d", value)


def encode_field_bool(field_number: int, value: bool) -> bytes:
    """Encode field tag + bool (als varint 0/1)."""
    return encode_field_varint(field_number, 1 if value else 0)


# ─── Decoder ──────────────────────────────────────────────────

@dataclass
class ProtoField:
    field_number: int
    wire_type: int
    value: object  # int, float, bytes, of str (poging)

    def as_string(self) -> str:
        if isinstance(self.value, bytes):
            try:
                return self.value.decode("utf-8")
            except UnicodeDecodeError:
                return repr(self.value)
        return str(self.value)

    def as_submessage(self) -> list["ProtoField"]:
        """Probeer de bytes als nested protobuf message te decoderen."""
        if isinstance(self.value, bytes):
            try:
                return decode_protobuf(self.value)
            except Exception:
                return []
        return []


def decode_varint(data: bytes, offset: int) -> tuple[int, int]:
    """Decode een varint, return (value, new_offset)."""
    result = 0
    shift = 0
    while offset < len(data):
        byte = data[offset]
        result |= (byte & 0x7F) << shift
        offset += 1
        if not (byte & 0x80):
            break
        shift += 7
    return result, offset


def decode_protobuf(data: bytes) -> list[ProtoField]:
    """Decode raw protobuf bytes naar een lijst van velden."""
    fields = []
    offset = 0
    while offset < len(data):
        tag, offset = decode_varint(data, offset)
        field_number = tag >> 3
        wire_type = tag & 0x07

        if wire_type == WIRE_VARINT:
            value, offset = decode_varint(data, offset)
            fields.append(ProtoField(field_number, wire_type, value))

        elif wire_type == WIRE_64BIT:
            value = struct.unpack("<d", data[offset:offset + 8])[0]
            offset += 8
            fields.append(ProtoField(field_number, wire_type, value))

        elif wire_type == WIRE_LENGTH_DELIMITED:
            length, offset = decode_varint(data, offset)
            value = data[offset:offset + length]
            offset += length
            fields.append(ProtoField(field_number, wire_type, value))

        elif wire_type == WIRE_32BIT:
            value = struct.unpack("<f", data[offset:offset + 4])[0]
            offset += 4
            fields.append(ProtoField(field_number, wire_type, value))

        else:
            break  # onbekend wire type

    return fields


def pretty_print_protobuf(data: bytes, indent: int = 0) -> str:
    """Recursief protobuf decoderen en mooi printen."""
    lines = []
    prefix = "  " * indent
    try:
        fields = decode_protobuf(data)
    except Exception:
        return f"{prefix}[raw bytes: {data.hex()}]"

    for field in fields:
        if field.wire_type == WIRE_LENGTH_DELIMITED and isinstance(field.value, bytes):
            # Probeer als string
            try:
                text = field.value.decode("utf-8")
                if all(32 <= ord(c) < 127 or c in "\n\r\t" for c in text):
                    lines.append(f'{prefix}field {field.field_number}: "{text}"')
                    continue
            except UnicodeDecodeError:
                pass

            # Probeer als nested message
            try:
                sub_fields = decode_protobuf(field.value)
                if sub_fields and len(sub_fields) > 0:
                    lines.append(f"{prefix}field {field.field_number}: {{")
                    lines.append(pretty_print_protobuf(field.value, indent + 1))
                    lines.append(f"{prefix}}}")
                    continue
            except Exception:
                pass

            lines.append(f"{prefix}field {field.field_number}: [bytes: {field.value.hex()[:60]}...]")

        elif field.wire_type == WIRE_64BIT:
            lines.append(f"{prefix}field {field.field_number}: {field.value:.2f} (double)")

        else:
            lines.append(f"{prefix}field {field.field_number}: {field.value}")

    return "\n".join(lines)


# ─── gRPC-Web Frame Encoding/Decoding ────────────────────────

def grpc_web_encode(protobuf_bytes: bytes) -> str:
    """Encode protobuf bytes als gRPC-Web-Text (base64)."""
    # gRPC frame: flag (0x00) + 4-byte big-endian length + payload
    frame = b"\x00" + struct.pack(">I", len(protobuf_bytes)) + protobuf_bytes
    return base64.b64encode(frame).decode("ascii")


def grpc_web_decode(grpc_web_text: str) -> bytes:
    """Decode gRPC-Web-Text (base64) naar protobuf bytes."""
    raw = base64.b64decode(grpc_web_text)

    # Er kunnen meerdere frames zijn (data + trailers)
    # Data frame: flag=0x00, Trailer frame: flag=0x80
    offset = 0
    messages = []

    while offset < len(raw):
        if offset + 5 > len(raw):
            break
        flag = raw[offset]
        length = struct.unpack(">I", raw[offset + 1:offset + 5])[0]
        offset += 5

        if offset + length > len(raw):
            break

        payload = raw[offset:offset + length]
        offset += length

        if flag == 0x00:
            # Data frame
            messages.append(payload)
        # flag == 0x80 = trailer frame (skip)

    return b"".join(messages)
