"""
Minimal AMF0 / AMF3 codec for handling Flash's NetConnection "Flash Remoting"
calls over plain HTTP (Content-Type: application/x-amf).

This is NOT a complete AMF implementation. It supports exactly what's needed
to (a) read the target/response names out of an incoming request envelope,
and (b) write back plain Python values (None/bool/int/float/str/dict/list)
as a valid AMF3-encoded response, wrapped in an AMF0 envelope.

No reference-table compression is used on encode (always writes full values).
That's legal per the AMF3 spec - decoders must accept it - it's just less
compact than a real implementation would be.
"""
import struct


# ---------------------------------------------------------------------------
# AMF3 encoding (used for the VALUE portion of each response body)
# ---------------------------------------------------------------------------

def _u29(n):
    n &= 0x1FFFFFFF
    if n < 0x80:
        return bytes([n])
    if n < 0x4000:
        return bytes([(n >> 7) | 0x80, n & 0x7F])
    if n < 0x200000:
        return bytes([(n >> 14) | 0x80, ((n >> 7) & 0x7F) | 0x80, n & 0x7F])
    return bytes([(n >> 22) | 0x80, ((n >> 15) & 0x7F) | 0x80,
                  ((n >> 8) & 0x7F) | 0x80, n & 0xFF])


def _amf3_str(s):
    b = s.encode("utf-8")
    return _u29((len(b) << 1) | 1) + b


def encode_amf3(v):
    if v is None:
        return b"\x01"
    if isinstance(v, bool):
        return b"\x03" if v else b"\x02"
    if isinstance(v, int):
        if -268435456 <= v <= 268435455:
            return b"\x04" + _u29(v)
        return b"\x05" + struct.pack(">d", float(v))
    if isinstance(v, float):
        return b"\x05" + struct.pack(">d", v)
    if isinstance(v, str):
        return b"\x06" + _amf3_str(v)
    if isinstance(v, dict):
        out = b"\x0A" + _u29(0x0B) + _amf3_str("")  # dynamic, 0 sealed members
        for k, val in v.items():
            out += _amf3_str(str(k)) + encode_amf3(val)
        out += _amf3_str("")  # terminator
        return out
    if isinstance(v, (list, tuple)):
        out = b"\x09" + _u29((len(v) << 1) | 1) + _amf3_str("")
        for item in v:
            out += encode_amf3(item)
        return out
    return b"\x06" + _amf3_str(str(v))


# ---------------------------------------------------------------------------
# AMF0 envelope parsing (request) / building (response)
# ---------------------------------------------------------------------------

class Body:
    __slots__ = ("target", "response", "value_bytes")

    def __init__(self, target, response, value_bytes):
        self.target = target
        self.response = response
        self.value_bytes = value_bytes


def _read_u16(buf, pos):
    return struct.unpack_from(">H", buf, pos)[0], pos + 2


def _read_s32(buf, pos):
    return struct.unpack_from(">i", buf, pos)[0], pos + 4


def _read_amf0_string(buf, pos):
    length, pos = _read_u16(buf, pos)
    if pos + length > len(buf):
        raise ValueError("truncated AMF0 string")
    s = buf[pos:pos + length].decode("utf-8", errors="replace")
    return s, pos + length


def parse_request(data):
    """Parse an incoming AMF remoting request. Returns (version, [Body,...])."""
    pos = 0
    version, pos = _read_u16(data, pos)
    header_count, pos = _read_u16(data, pos)
    for _ in range(header_count):
        _name, pos = _read_amf0_string(data, pos)
        _mustUnderstand = data[pos]
        pos += 1
        length, pos = _read_s32(data, pos)
        pos += length  # skip header value bytes entirely
    body_count, pos = _read_u16(data, pos)
    bodies = []
    for _ in range(body_count):
        target, pos = _read_amf0_string(data, pos)
        response, pos = _read_amf0_string(data, pos)
        length, pos = _read_s32(data, pos)
        if length < 0:
            # Unknown length - treat the remainder as this body's value.
            value_bytes = data[pos:]
            pos = len(data)
        else:
            value_bytes = data[pos:pos + length]
            pos += length
        bodies.append(Body(target, response, value_bytes))
    return version, bodies


def build_response(version, responses):
    """responses: list of (response_name, python_value). Builds a full AMF envelope."""
    out = struct.pack(">H", version)  # echo back client's version
    out += struct.pack(">H", 0)       # no headers
    out += struct.pack(">H", len(responses))
    for response_name, value in responses:
        target = response_name + "/onResult"
        out += struct.pack(">H", len(target)) + target.encode("utf-8")
        out += struct.pack(">H", len("null")) + b"null"
        value_bytes = b"\x11" + encode_amf3(value)  # 0x11 = AVM+ (AMF3) marker
        out += struct.pack(">i", len(value_bytes))
        out += value_bytes
    return out


# ---------------------------------------------------------------------------
# Request-argument decoding. NetConnection uses an AMF0 strict array for
# its argument list, with marker 0x11 when an individual value switches to
# AMF3. The prior decoder assumed the entire argument list was AMF3, so
# placement and purchase calls silently failed to update the save. Keep
# decoding failures local to the affected action; never write guessed data.
# ---------------------------------------------------------------------------

def _read_u29(buf, pos):
    result = 0
    for i in range(4):
        if pos >= len(buf):
            raise ValueError("truncated u29")
        b = buf[pos]
        pos += 1
        if i == 3:
            result = (result << 8) | b
            break
        result = (result << 7) | (b & 0x7F)
        if not (b & 0x80):
            break
    return result, pos


def _decode_amf3_string_bare(buf, pos, strings):
    """A U29S-ref-prefixed string with no leading 0x06 type marker - used for
    array associative-part keys, which are always strings but (per the AMF3
    spec) don't carry their own type byte in that position."""
    ref, pos = _read_u29(buf, pos)
    if (ref & 1) == 0:
        idx = ref >> 1
        if idx >= len(strings):
            raise ValueError("invalid AMF3 string reference")
        return strings[idx], pos
    length = ref >> 1
    if pos + length > len(buf):
        raise ValueError("truncated string")
    s = buf[pos:pos + length].decode("utf-8", errors="replace")
    pos += length
    if s:
        strings.append(s)
    return s, pos


def decode_amf3(buf, pos, strings=None, objects=None, traits=None, depth=0):
    """Decode the AMF3 value types used by NetConnection arguments.

    Keep the string, object, and trait reference tables across nested values;
    Flash reuses anonymous-object traits in placement queues. Unsupported
    types fail closed so a save handler never persists a misread placement.
    """
    if strings is None:
        strings = []
    if objects is None:
        objects = []
    if traits is None:
        traits = []
    if depth > 64:
        raise ValueError("AMF3 nesting too deep")
    if pos >= len(buf):
        raise ValueError("truncated amf3 value")
    marker = buf[pos]
    pos += 1
    if marker in (0x00, 0x01):  # undefined, null
        return None, pos
    if marker == 0x02:
        return False, pos
    if marker == 0x03:
        return True, pos
    if marker == 0x04:  # integer, 29-bit signed
        val, pos = _read_u29(buf, pos)
        if val & 0x10000000:
            val -= 0x20000000
        return val, pos
    if marker == 0x05:  # double
        if pos + 8 > len(buf):
            raise ValueError("truncated double")
        return struct.unpack_from(">d", buf, pos)[0], pos + 8
    if marker == 0x06:  # string
        return _decode_amf3_string_bare(buf, pos, strings)
    if marker == 0x09:  # array
        ref, pos = _read_u29(buf, pos)
        if (ref & 1) == 0:
            idx = ref >> 1
            if idx >= len(objects):
                raise ValueError("invalid AMF3 array reference")
            return objects[idx], pos
        dense_len = ref >> 1
        if dense_len > 100000:
            raise ValueError("AMF3 array too large")
        dense = []
        object_idx = len(objects)
        objects.append(dense)
        assoc = {}
        while True:
            key, pos = _decode_amf3_string_bare(buf, pos, strings)
            if key == "":
                break
            val, pos = decode_amf3(buf, pos, strings, objects, traits, depth + 1)
            assoc[key] = val
        for _ in range(dense_len):
            val, pos = decode_amf3(buf, pos, strings, objects, traits, depth + 1)
            dense.append(val)
        if assoc:
            assoc["__dense__"] = dense
            objects[object_idx] = assoc
            return assoc, pos
        return dense, pos
    if marker == 0x0A:  # object
        ref, pos = _read_u29(buf, pos)
        if (ref & 1) == 0:
            idx = ref >> 1
            if idx >= len(objects):
                raise ValueError("invalid AMF3 object reference")
            return objects[idx], pos
        if (ref & 3) == 1:
            idx = ref >> 2
            if idx >= len(traits):
                raise ValueError("invalid AMF3 trait reference")
            sealed_names, dynamic = traits[idx]
        else:
            if ref & 4:
                raise ValueError("externalizable AMF3 object is unsupported")
            dynamic = bool(ref & 8)
            sealed_count = ref >> 4
            if sealed_count > 10000:
                raise ValueError("AMF3 object has too many sealed members")
            _class_name, pos = _decode_amf3_string_bare(buf, pos, strings)
            sealed_names = []
            for _ in range(sealed_count):
                name, pos = _decode_amf3_string_bare(buf, pos, strings)
                sealed_names.append(name)
            traits.append((sealed_names, dynamic))
        obj = {}
        objects.append(obj)
        for key in sealed_names:
            obj[key], pos = decode_amf3(buf, pos, strings, objects, traits, depth + 1)
        if dynamic:
            while True:
                key, pos = _decode_amf3_string_bare(buf, pos, strings)
                if key == "":
                    break
                obj[key], pos = decode_amf3(buf, pos, strings, objects, traits, depth + 1)
        return obj, pos
    raise ValueError("unsupported or unrecognized AMF3 marker: 0x%02x" % marker)


def decode_amf3_args(value_bytes):
    """Decode an argument list that is entirely inside an AMF3 bridge.

    Most game calls instead use the AMF0 strict-array form handled by
    decode_amf_args().
    """
    if not value_bytes or value_bytes[0] != 0x11:
        raise ValueError("value_bytes doesn't start with the 0x11 AVM+ marker")
    value, pos = decode_amf3(value_bytes, 1, [], [], [])
    if pos != len(value_bytes):
        raise ValueError("trailing bytes after AMF3 arguments")
    if isinstance(value, dict):
        return value.get("__dense__", [])
    if isinstance(value, list):
        return value
    return [value]


def _decode_amf0_value(buf, pos, references, amf3_state, depth=0):
    """Decode one AMF0 value, including its AMF3 bridge marker (0x11)."""
    if depth > 64 or pos >= len(buf):
        raise ValueError("truncated or excessively nested AMF0 value")
    marker = buf[pos]
    pos += 1
    if marker == 0x00:  # number
        if pos + 8 > len(buf):
            raise ValueError("truncated AMF0 number")
        return struct.unpack_from(">d", buf, pos)[0], pos + 8
    if marker == 0x01:  # boolean
        if pos >= len(buf):
            raise ValueError("truncated AMF0 boolean")
        return buf[pos] != 0, pos + 1
    if marker == 0x02:  # string
        length, pos = _read_u16(buf, pos)
        if pos + length > len(buf):
            raise ValueError("truncated AMF0 string")
        return buf[pos:pos + length].decode("utf-8", "replace"), pos + length
    if marker in (0x05, 0x06, 0x0D):  # null, undefined, unsupported
        return None, pos
    if marker == 0x07:  # reference to a prior complex AMF0 value
        idx, pos = _read_u16(buf, pos)
        if idx >= len(references):
            raise ValueError("invalid AMF0 reference")
        return references[idx], pos
    if marker == 0x0A:  # strict array
        if pos + 4 > len(buf):
            raise ValueError("truncated AMF0 array")
        count = struct.unpack_from(">I", buf, pos)[0]
        pos += 4
        if count > 100000:
            raise ValueError("AMF0 array too large")
        result = []
        references.append(result)
        for _ in range(count):
            item, pos = _decode_amf0_value(buf, pos, references, amf3_state, depth + 1)
            result.append(item)
        return result, pos
    if marker in (0x03, 0x08, 0x10):  # object, ECMA array, typed object
        if marker == 0x08:
            if pos + 4 > len(buf):
                raise ValueError("truncated AMF0 ECMA array")
            pos += 4  # associative count; the end marker is authoritative
        elif marker == 0x10:
            _class_name, pos = _read_amf0_string(buf, pos)
        result = {}
        references.append(result)
        while True:
            key, pos = _read_amf0_string(buf, pos)
            if not key and pos < len(buf) and buf[pos] == 0x09:
                pos += 1
                break
            value, pos = _decode_amf0_value(buf, pos, references, amf3_state, depth + 1)
            result[key] = value
        return result, pos
    if marker == 0x0C or marker == 0x0F:  # long string or XML document
        if pos + 4 > len(buf):
            raise ValueError("truncated AMF0 long string")
        length = struct.unpack_from(">I", buf, pos)[0]
        pos += 4
        if pos + length > len(buf):
            raise ValueError("truncated AMF0 long string content")
        return buf[pos:pos + length].decode("utf-8", "replace"), pos + length
    if marker == 0x0B:  # date: milliseconds since epoch and timezone offset
        if pos + 10 > len(buf):
            raise ValueError("truncated AMF0 date")
        return struct.unpack_from(">d", buf, pos)[0], pos + 10
    if marker == 0x11:  # AVM+ bridge to AMF3
        return decode_amf3(buf, pos, *amf3_state, depth=depth + 1)
    raise ValueError("unsupported AMF0 marker: 0x%02x" % marker)


def decode_amf_args(value_bytes):
    """Decode a NetConnection request's arguments, AMF0 or AMF3.

    AMF0 packets use a strict array for the argument list. Individual
    complex arguments can switch to AMF3 with marker 0x11. This game sends
    the account id, signature, and POPCAP id before service-specific args.
    """
    if not value_bytes:
        raise ValueError("empty AMF argument body")
    if value_bytes[0] == 0x11:
        return decode_amf3_args(value_bytes)
    try:
        value, pos = _decode_amf0_value(value_bytes, 0, [], ([], [], []))
    except struct.error as exc:
        raise ValueError("truncated AMF0 arguments") from exc
    if pos != len(value_bytes) or not isinstance(value, list):
        raise ValueError("AMF0 arguments are not a complete strict array")
    return value
