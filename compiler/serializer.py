"""
SEQUENT Compiler - Binary Bytecode Serialization
Implements genuine binary serialization (.seqc) for CompiledProgram instances
with magic header, format versioning, and real CRC32 verification.
"""

from io import BytesIO
from pathlib import Path
import struct
from typing import Any, Dict, List, Tuple
import zlib

from compiler.bytecode import BytecodeInstruction, CompiledProgram, OpCode

# Binary Format Constants
SEQC_MAGIC = b"SEQC"        # 4 bytes magic signature
SEQC_VERSION = 1            # 2 bytes format version
HEADER_STRUCT = ">4sHHII"   # Magic(4s), Version(H), Flags(H), PayloadLen(I), CRC32(I) = 16 bytes
HEADER_SIZE = struct.calcsize(HEADER_STRUCT)

# Value Type Identifiers
TYPE_NONE = 0
TYPE_INT = 1
TYPE_FLOAT = 2
TYPE_STRING = 3
TYPE_BOOL = 4
TYPE_TUPLE2 = 5
TYPE_TUPLE3 = 6


class SerializationError(Exception):
    """Exception raised for corrupted, truncated, or invalid .seqc files."""
    pass


class BytecodeSerializer:
    """Serializes and deserializes SEQUENT CompiledProgram instances into binary .seqc format."""

    @classmethod
    def serialize(cls, compiled: CompiledProgram) -> bytes:
        """Serializes a CompiledProgram into binary bytes with header and CRC32."""
        payload = cls._encode_payload(compiled)
        crc32_val = zlib.crc32(payload) & 0xFFFFFFFF
        header = struct.pack(
            HEADER_STRUCT,
            SEQC_MAGIC,
            SEQC_VERSION,
            0,  # flags
            len(payload),
            crc32_val,
        )
        return header + payload

    @classmethod
    def deserialize(cls, data: bytes) -> CompiledProgram:
        """Deserializes binary bytes into a verified CompiledProgram."""
        if len(data) < HEADER_SIZE:
            raise SerializationError(f"Truncated .seqc file: expected at least {HEADER_SIZE} bytes, got {len(data)}")

        magic, version, flags, payload_len, crc_expected = struct.unpack(HEADER_STRUCT, data[:HEADER_SIZE])

        if magic != SEQC_MAGIC:
            raise SerializationError(f"Invalid magic header: expected {SEQC_MAGIC!r}, got {magic!r}")

        if version != SEQC_VERSION:
            raise SerializationError(f"Unsupported .seqc format version: {version} (supported version: {SEQC_VERSION})")

        payload = data[HEADER_SIZE:]
        if len(payload) != payload_len:
            raise SerializationError(f"Truncated payload: expected {payload_len} bytes, got {len(payload)}")

        crc_actual = zlib.crc32(payload) & 0xFFFFFFFF
        if crc_actual != crc_expected:
            raise SerializationError(
                f"CRC32 Checksum mismatch: file payload is corrupted! (expected 0x{crc_expected:08X}, got 0x{crc_actual:08X})"
            )

        return cls._decode_payload(payload)

    @classmethod
    def save(cls, compiled: CompiledProgram, filepath: str) -> int:
        """Serializes and writes a CompiledProgram to a .seqc binary file."""
        data = cls.serialize(compiled)
        Path(filepath).write_bytes(data)
        return len(data)

    @classmethod
    def load(cls, filepath: str) -> CompiledProgram:
        """Reads and deserializes a .seqc binary file."""
        path = Path(filepath)
        if not path.exists():
            raise FileNotFoundError(f"Bytecode file '{filepath}' not found.")
        data = path.read_bytes()
        return cls.deserialize(data)

    # -------------------------------------------------------------
    # Internal Binary Packing Helpers
    # -------------------------------------------------------------
    @classmethod
    def _write_str(cls, buf: BytesIO, s: str) -> None:
        enc = s.encode("utf-8")
        buf.write(struct.pack(">H", len(enc)))
        buf.write(enc)

    @classmethod
    def _read_str(cls, buf: BytesIO) -> str:
        data = buf.read(2)
        if len(data) < 2:
            raise SerializationError("Unexpected EOF while reading string length")
        str_len = struct.unpack(">H", data)[0]
        s_data = buf.read(str_len)
        if len(s_data) < str_len:
            raise SerializationError("Unexpected EOF while reading string data")
        return s_data.decode("utf-8")

    @classmethod
    def _write_value(cls, buf: BytesIO, val: Any) -> None:
        if val is None:
            buf.write(struct.pack(">B", TYPE_NONE))
        elif isinstance(val, bool):
            buf.write(struct.pack(">BB", TYPE_BOOL, 1 if val else 0))
        elif isinstance(val, int):
            buf.write(struct.pack(">Bq", TYPE_INT, val))
        elif isinstance(val, float):
            buf.write(struct.pack(">Bd", TYPE_FLOAT, val))
        elif isinstance(val, str):
            buf.write(struct.pack(">B", TYPE_STRING))
            cls._write_str(buf, val)
        elif isinstance(val, tuple):
            if len(val) == 2:
                buf.write(struct.pack(">B", TYPE_TUPLE2))
                cls._write_str(buf, str(val[0]))
                buf.write(struct.pack(">q", int(val[1])))
            elif len(val) == 3:
                buf.write(struct.pack(">B", TYPE_TUPLE3))
                cls._write_str(buf, str(val[0]))
                cls._write_str(buf, str(val[1]))
                buf.write(struct.pack(">q", int(val[2])))
            else:
                raise SerializationError(f"Unsupported tuple length: {len(val)}")
        else:
            raise SerializationError(f"Unsupported value type for serialization: {type(val)}")

    @classmethod
    def _read_value(cls, buf: BytesIO) -> Any:
        tag_data = buf.read(1)
        if not tag_data:
            raise SerializationError("Unexpected EOF while reading value tag")
        tag = struct.unpack(">B", tag_data)[0]

        if tag == TYPE_NONE:
            return None
        elif tag == TYPE_BOOL:
            return struct.unpack(">B", buf.read(1))[0] != 0
        elif tag == TYPE_INT:
            return struct.unpack(">q", buf.read(8))[0]
        elif tag == TYPE_FLOAT:
            return struct.unpack(">d", buf.read(8))[0]
        elif tag == TYPE_STRING:
            return cls._read_str(buf)
        elif tag == TYPE_TUPLE2:
            s = cls._read_str(buf)
            i = struct.unpack(">q", buf.read(8))[0]
            return (s, i)
        elif tag == TYPE_TUPLE3:
            s1 = cls._read_str(buf)
            s2 = cls._read_str(buf)
            i = struct.unpack(">q", buf.read(8))[0]
            return (s1, s2, i)
        else:
            raise SerializationError(f"Invalid value type tag: {tag}")

    @classmethod
    def _encode_payload(cls, compiled: CompiledProgram) -> bytes:
        buf = BytesIO()

        # 1. System Name
        cls._write_str(buf, compiled.system_name)

        # 2. Initial States: count -> (name, value)
        buf.write(struct.pack(">H", len(compiled.initial_states)))
        for k, v in compiled.initial_states.items():
            cls._write_str(buf, k)
            cls._write_value(buf, v)

        # 3. State Types: count -> (name, type_str)
        buf.write(struct.pack(">H", len(compiled.state_types)))
        for k, v in compiled.state_types.items():
            cls._write_str(buf, k)
            cls._write_str(buf, v)

        # 4. Events: count -> name
        buf.write(struct.pack(">H", len(compiled.events)))
        for ev in compiled.events:
            cls._write_str(buf, ev)

        # 5. Constraints: count -> (source, target, duration_ms, raw_dur, line)
        buf.write(struct.pack(">H", len(compiled.constraints)))
        for c in compiled.constraints:
            cls._write_str(buf, c["source"])
            cls._write_str(buf, c["target"])
            buf.write(struct.pack(">I", int(c["duration_ms"])))
            cls._write_str(buf, c["raw_duration"])
            buf.write(struct.pack(">I", int(c["line"])))

        # 6. Handler Table: count -> (event_name, offset)
        buf.write(struct.pack(">H", len(compiled.handler_table)))
        for ev, off in compiled.handler_table.items():
            cls._write_str(buf, ev)
            buf.write(struct.pack(">I", int(off)))

        # 7. Instructions: count -> (offset, opcode_id, arg, source_line, comment)
        opcode_to_id = {op: i for i, op in enumerate(OpCode)}
        buf.write(struct.pack(">I", len(compiled.instructions)))
        for inst in compiled.instructions:
            op_id = opcode_to_id.get(inst.opcode)
            if op_id is None:
                raise SerializationError(f"Unknown opcode: {inst.opcode}")
            buf.write(struct.pack(">IBI", inst.offset, op_id, inst.source_line))
            cls._write_value(buf, inst.arg)
            cls._write_str(buf, inst.comment)

        return buf.getvalue()

    @classmethod
    def _decode_payload(cls, payload: bytes) -> CompiledProgram:
        buf = BytesIO(payload)
        id_to_opcode = {i: op for i, op in enumerate(OpCode)}

        # 1. System Name
        system_name = cls._read_str(buf)

        # 2. Initial States
        init_state_count = struct.unpack(">H", buf.read(2))[0]
        initial_states = {}
        for _ in range(init_state_count):
            k = cls._read_str(buf)
            v = cls._read_value(buf)
            initial_states[k] = v

        # 3. State Types
        state_type_count = struct.unpack(">H", buf.read(2))[0]
        state_types = {}
        for _ in range(state_type_count):
            k = cls._read_str(buf)
            v = cls._read_str(buf)
            state_types[k] = v

        # 4. Events
        event_count = struct.unpack(">H", buf.read(2))[0]
        events = [cls._read_str(buf) for _ in range(event_count)]

        # 5. Constraints
        constraint_count = struct.unpack(">H", buf.read(2))[0]
        constraints = []
        for _ in range(constraint_count):
            src = cls._read_str(buf)
            tgt = cls._read_str(buf)
            dur_ms = struct.unpack(">I", buf.read(4))[0]
            raw_dur = cls._read_str(buf)
            line = struct.unpack(">I", buf.read(4))[0]
            constraints.append({
                "source": src,
                "target": tgt,
                "duration_ms": dur_ms,
                "raw_duration": raw_dur,
                "line": line,
            })

        # 6. Handler Table
        handler_count = struct.unpack(">H", buf.read(2))[0]
        handler_table = {}
        for _ in range(handler_count):
            ev = cls._read_str(buf)
            off = struct.unpack(">I", buf.read(4))[0]
            handler_table[ev] = off

        # 7. Instructions
        inst_count = struct.unpack(">I", buf.read(4))[0]
        instructions = []
        for _ in range(inst_count):
            off, op_id, line = struct.unpack(">IBI", buf.read(9))
            if op_id not in id_to_opcode:
                raise SerializationError(f"Invalid opcode ID in serialized bytecode: {op_id}")
            opcode = id_to_opcode[op_id]
            arg = cls._read_value(buf)
            comment = cls._read_str(buf)
            instructions.append(BytecodeInstruction(
                offset=off,
                opcode=opcode,
                arg=arg,
                source_line=line,
                comment=comment,
            ))

        return CompiledProgram(
            system_name=system_name,
            initial_states=initial_states,
            state_types=state_types,
            events=events,
            constraints=constraints,
            instructions=instructions,
            handler_table=handler_table,
        )


def serialize_program(compiled: CompiledProgram) -> bytes:
    """Convenience function to serialize a CompiledProgram to binary bytes."""
    return BytecodeSerializer.serialize(compiled)


def deserialize_program(data: bytes) -> CompiledProgram:
    """Convenience function to deserialize binary bytes to a CompiledProgram."""
    return BytecodeSerializer.deserialize(data)


def save_seqc(compiled: CompiledProgram, filepath: str) -> int:
    """Convenience function to save a CompiledProgram to a .seqc binary file."""
    return BytecodeSerializer.save(compiled, filepath)


def load_seqc(filepath: str) -> CompiledProgram:
    """Convenience function to load a CompiledProgram from a .seqc binary file."""
    return BytecodeSerializer.load(filepath)
