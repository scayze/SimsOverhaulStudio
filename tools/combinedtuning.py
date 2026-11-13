"""Minimal CombinedTuning (0x62E94D38) binary DATA -> XML decoder.

Adapted from the MIT-licensed sims4-workspace datamining decoder.
"""
import struct


RELOFFSET_NULL = -0x80000000


class BinaryDecoder:
    def __init__(self, data):
        self._data = data
        self._pos = 0

    def tell(self):
        return self._pos

    def seek(self, pos):
        self._pos = pos

    def uint8(self):
        v = self._data[self._pos]
        self._pos += 1
        return v

    def int16(self):
        v = struct.unpack_from("<h", self._data, self._pos)[0]
        self._pos += 2
        return v

    def uint16(self):
        v = struct.unpack_from("<H", self._data, self._pos)[0]
        self._pos += 2
        return v

    def int32(self):
        v = struct.unpack_from("<i", self._data, self._pos)[0]
        self._pos += 4
        return v

    def uint32(self):
        v = struct.unpack_from("<I", self._data, self._pos)[0]
        self._pos += 4
        return v

    def uint64(self):
        v = struct.unpack_from("<Q", self._data, self._pos)[0]
        self._pos += 8
        return v

    def float32(self):
        v = struct.unpack_from("<f", self._data, self._pos)[0]
        self._pos += 4
        return v

    def string(self):
        end = self._data.index(b"\x00", self._pos)
        s = self._data[self._pos:end].decode("utf-8", "replace")
        self._pos = end + 1
        return s

    def chars_utf8(self, n):
        s = self._data[self._pos:self._pos + n].decode("utf-8", "replace")
        self._pos += n
        return s


class DataType:
    Boolean = 0
    Character = 1
    Int8 = 2
    UInt8 = 3
    Int16 = 4
    UInt16 = 5
    Int32 = 6
    UInt32 = 7
    Int64 = 8
    UInt64 = 9
    Float = 10
    String = 11
    HashedString = 12
    Object = 13
    Vector = 14
    Float2 = 15
    Float3 = 16
    Float4 = 17
    TableSetReference = 18
    ResourceKey = 19
    LocalizationKey = 20
    Variant = 21
    Undefined = 22

    @staticmethod
    def alignment(dt):
        if dt in (0, 1, 2, 3):
            return 1
        if dt in (4, 5):
            return 2
        if dt in (6, 7, 10, 11, 12, 13, 14, 15, 16, 17, 20, 21):
            return 4
        if dt in (8, 9, 18, 19):
            return 8
        return 1


class TableInfo:
    __slots__ = ("name", "name_hash", "schema_offset_pos", "schema_offset",
                 "data_type", "row_size", "row_offset_pos", "row_offset", "row_count")


class SchemaColumn:
    __slots__ = ("name", "name_hash", "data_type", "flags", "offset", "schema_offset")


class Schema:
    __slots__ = ("name", "name_hash", "schema_hash", "schema_size", "column_offset_pos",
                 "column_offset", "num_columns", "columns", "name_offset_pos")


def _read_string_at(decoder, offset):
    if offset == RELOFFSET_NULL:
        return None
    saved = decoder.tell()
    decoder.seek(offset)
    s = decoder.string()
    decoder.seek(saved)
    return s


def _seek_to_alignment(decoder, mask):
    pos = decoder.tell()
    decoder.seek(pos + (-pos & mask))


def _read_data_type(decoder, type_code):
    if type_code in (DataType.Boolean, DataType.UInt8, DataType.Int8):
        return decoder.uint8()
    if type_code == DataType.Character:
        return chr(decoder.uint8())
    if type_code == DataType.Int16:
        return decoder.int16()
    if type_code == DataType.UInt16:
        return decoder.uint16()
    if type_code == DataType.Int32:
        return decoder.int32()
    if type_code == DataType.UInt32:
        return decoder.uint32()
    if type_code in (DataType.Int64, DataType.UInt64):
        return decoder.uint64()
    if type_code == DataType.Float:
        return decoder.float32()
    if type_code == DataType.String:
        return {"startof_mDataOffset": decoder.tell(), "mDataOffset": decoder.int32()}
    if type_code == DataType.HashedString:
        pos = decoder.tell()
        return {"startof_mDataOffset": pos, "mDataOffset": decoder.int32(), "mHash": decoder.uint32()}
    if type_code == DataType.Object:
        return {"startof_mDataOffset": decoder.tell(), "mDataOffset": decoder.int32()}
    if type_code == DataType.Vector:
        pos = decoder.tell()
        return {"startof_mDataOffset": pos, "mDataOffset": decoder.int32(), "mCount": decoder.uint32()}
    if type_code == DataType.Float2:
        return (decoder.float32(), decoder.float32())
    if type_code == DataType.Float3:
        return (decoder.float32(), decoder.float32(), decoder.float32())
    if type_code == DataType.Float4:
        return (decoder.float32(), decoder.float32(), decoder.float32(), decoder.float32())
    if type_code == DataType.TableSetReference:
        return decoder.uint64()
    if type_code == DataType.ResourceKey:
        return {"instance": decoder.uint64(), "type": decoder.uint32(), "group": decoder.uint32()}
    if type_code == DataType.LocalizationKey:
        return decoder.uint32()
    if type_code == DataType.Variant:
        pos = decoder.tell()
        return {"startof_mDataOffset": pos, "mDataOffset": decoder.int32(), "mTypeHash": decoder.uint32()}
    raise ValueError("Unknown type code: {}".format(type_code))


def parse_binary_data(data):
    decoder = BinaryDecoder(data)
    magic = decoder.chars_utf8(4)
    if magic != "DATA":
        raise ValueError("Not a DATA file (got {!r})".format(magic))
    version = decoder.uint32()
    if version < 0x100 or version > 0x101:
        raise ValueError("Unknown DATA version")
    table_header_pos = decoder.tell()
    table_header_offset = decoder.int32()
    num_tables = decoder.int32()
    schema_pos = decoder.tell()
    schema_offset = decoder.int32()
    num_schemas = decoder.int32()
    if version >= 0x101:
        decoder.uint32()

    decoder.seek(table_header_pos + table_header_offset)
    tables = []
    for _ in range(num_tables):
        t = TableInfo()
        name_offset_pos = decoder.tell()
        name_offset = decoder.int32()
        t.name_hash = decoder.uint32()
        t.name = _read_string_at(decoder, name_offset_pos + name_offset) if name_offset != RELOFFSET_NULL else None
        t.schema_offset_pos = decoder.tell()
        t.schema_offset = decoder.int32()
        t.data_type = decoder.uint32()
        t.row_size = decoder.uint32()
        t.row_offset_pos = decoder.tell()
        t.row_offset = decoder.int32()
        t.row_count = decoder.uint32()
        tables.append(t)

    row_data_start = decoder.tell()

    decoder.seek(schema_pos + schema_offset)
    schemas = []
    last_column_end = 0
    for _ in range(num_schemas):
        s = Schema()
        s.name_offset_pos = decoder.tell()
        name_offset = decoder.int32()
        s.name_hash = decoder.uint32()
        s.name = _read_string_at(decoder, s.name_offset_pos + name_offset) if name_offset != RELOFFSET_NULL else None
        s.schema_hash = decoder.uint32()
        s.schema_size = decoder.uint32()
        s.column_offset_pos = decoder.tell()
        s.column_offset = decoder.int32()
        s.num_columns = decoder.uint32()
        schema_end = decoder.tell()
        decoder.seek(s.column_offset_pos + s.column_offset)
        s.columns = []
        for _ in range(s.num_columns):
            col = SchemaColumn()
            col_name_pos = decoder.tell()
            col_name_offset = decoder.int32()
            col.name_hash = decoder.uint32()
            col.name = _read_string_at(decoder, col_name_pos + col_name_offset) if col_name_offset != RELOFFSET_NULL else None
            col.data_type = decoder.uint16()
            col.flags = decoder.uint16()
            col.offset = decoder.uint32()
            col.schema_offset = decoder.int32()
            s.columns.append(col)
        s.columns.sort(key=lambda c: c.offset)
        last_column_end = decoder.tell()
        decoder.seek(schema_end)
        schemas.append(s)

    decoder.seek(row_data_start)

    def get_schema_index(offset, row_size=0):
        for idx, sch in enumerate(schemas):
            if offset == sch.name_offset_pos:
                return idx
        if row_size > 0:
            for idx, sch in enumerate(schemas):
                if sch.schema_size == row_size:
                    return idx
        raise ValueError("Unknown schema at offset {}".format(offset))

    table_data = []
    for i in range(num_tables):
        _seek_to_alignment(decoder, 15)
        tbl = tables[i]
        rows = []
        for _ in range(tbl.row_count):
            if tbl.schema_offset == RELOFFSET_NULL:
                rows.append(_read_data_type(decoder, tbl.data_type))
                _seek_to_alignment(decoder, DataType.alignment(tbl.data_type) - 1)
            else:
                si = get_schema_index(tbl.schema_offset_pos + tbl.schema_offset, tbl.row_size)
                schema = schemas[si]
                row_start = decoder.tell()
                row = {}
                for col in schema.columns:
                    decoder.seek(row_start + col.offset)
                    row[col.name] = _read_data_type(decoder, col.data_type)
                decoder.seek(row_start + schema.schema_size)
                rows.append(row)
                _seek_to_alignment(decoder, 0)
        table_data.append(rows)
        _seek_to_alignment(decoder, 15)

    return tables, schemas, table_data, version


def _get_position(ref):
    offset = ref["mDataOffset"]
    if offset == RELOFFSET_NULL:
        return RELOFFSET_NULL
    return ref["startof_mDataOffset"] + offset


def _is_null(ref):
    return ref["mDataOffset"] == RELOFFSET_NULL


def decode_combined_tuning(data):
    tables, schemas, table_data, version = parse_binary_data(data)
    decoder = BinaryDecoder(data)
    if len(tables) < 7:
        raise ValueError("CombinedTuning DATA needs >= 7 tables")
    meta_rows, node_rows, attr_rows, node_refs, attr_refs, string_refs = table_data[:6]
    if not meta_rows:
        raise ValueError("Empty metadata")
    meta = meta_rows[0]
    table_offsets = []
    for tbl in tables:
        pos = tbl.row_offset_pos + tbl.row_offset
        table_offsets.append(pos + (-pos & 15))
    first_element_pos = _get_position(meta["first_element"])

    def row_index_at(position, table_index):
        return (position - table_offsets[table_index]) // tables[table_index].row_size

    def get_text(text_row):
        ref = string_refs[text_row]
        pos = _get_position(ref)
        saved = decoder.tell()
        decoder.seek(pos)
        s = decoder.string()
        decoder.seek(saved)
        return s

    def esc(s):
        return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")

    def read_attributes(first_attr_pos):
        attrs = []
        idx = row_index_at(first_attr_pos, 4)
        while idx < len(attr_refs):
            ref = attr_refs[idx]
            if _is_null(ref):
                break
            attr_pos = _get_position(ref)
            row = attr_rows[row_index_at(attr_pos, 2)]
            attrs.append((get_text(row["name"]), get_text(row["value"])))
            idx += 1
        return attrs

    def read_children(first_child_pos):
        children = []
        idx = row_index_at(first_child_pos, 3)
        while idx < len(node_refs):
            ref = node_refs[idx]
            if _is_null(ref):
                break
            children.append(read_node(_get_position(ref)))
            idx += 1
        return children

    def read_node(position):
        node = node_rows[row_index_at(position, 1)]
        text = get_text(node["text"])
        has_attrs = not _is_null(node["attrs"])
        has_children = not _is_null(node["children"])
        if not has_attrs and not has_children:
            if position >= first_element_pos:
                return "<{} />".format(esc(text))
            return esc(text)
        parts = ["<{}".format(text)]
        if has_attrs:
            for name, value in read_attributes(_get_position(node["attrs"])):
                parts.append(' {}="{}"'.format(name, esc(value)))
        if has_children:
            parts.append(">")
            parts.extend(read_children(_get_position(node["children"])))
            parts.append("</{}>".format(text))
        else:
            parts.append(" />")
        return "".join(parts)

    return '<?xml version="1.0" encoding="utf-8"?>\n' + read_node(_get_position(meta["top_element"]))
