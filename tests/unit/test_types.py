# pylint: disable=missing-docstring

import re

import pytest

from recap.types import (
    ALIAS_REGEX,
    BoolType,
    BytesType,
    EnumType,
    FloatType,
    IntType,
    ListType,
    MapType,
    NullType,
    ProxyType,
    RecapType,
    RecapTypeRegistry,
    StringType,
    StructType,
    UnionType,
    UnknownType,
    from_dict,
    to_dict,
)


def test_null_type():
    test_dict = {"type": "null"}
    recap_type = from_dict(test_dict)
    assert isinstance(recap_type, NullType)
    assert recap_type.type_ == "null"


def test_bool_type():
    test_dict = {"type": "bool"}
    recap_type = from_dict(test_dict)
    assert isinstance(recap_type, BoolType)
    assert recap_type.type_ == "bool"


def test_int_type():
    test_dict = {"type": "int", "bits": 32}
    recap_type = from_dict(test_dict)
    assert isinstance(recap_type, IntType)
    assert recap_type.type_ == "int"
    assert recap_type.bits == 32


def test_float_type():
    test_dict = {"type": "float", "bits": 64}
    recap_type = from_dict(test_dict)
    assert isinstance(recap_type, FloatType)
    assert recap_type.type_ == "float"
    assert recap_type.bits == 64


def test_string_type():
    test_dict = {"type": "string", "bytes": 32}
    recap_type = from_dict(test_dict)
    assert isinstance(recap_type, StringType)
    assert recap_type.type_ == "string"
    assert recap_type.bytes_ == 32


def test_bytes_type():
    test_dict = {"type": "bytes", "bytes": 32}
    recap_type = from_dict(test_dict)
    assert isinstance(recap_type, BytesType)
    assert recap_type.type_ == "bytes"
    assert recap_type.bytes_ == 32


def test_list_type():
    test_dict = {"type": "list", "values": {"type": "int", "bits": 32}}
    recap_type = from_dict(test_dict)
    assert isinstance(recap_type, ListType)
    assert recap_type.type_ == "list"
    assert isinstance(recap_type.values, IntType)
    assert recap_type.values.type_ == "int"
    assert recap_type.values.bits == 32


def test_map_type():
    test_dict = {
        "type": "map",
        "keys": {"type": "int", "bits": 32},
        "values": {"type": "string", "bytes": 32},
    }
    recap_type = from_dict(test_dict)
    assert isinstance(recap_type, MapType)
    assert recap_type.type_ == "map"
    assert isinstance(recap_type.keys, IntType)
    assert recap_type.keys.type_ == "int"
    assert recap_type.keys.bits == 32
    assert isinstance(recap_type.values, StringType)
    assert recap_type.values.type_ == "string"
    assert recap_type.values.bytes_ == 32


def test_struct_type():
    test_dict = {
        "type": "struct",
        "fields": [{"type": "int", "bits": 32}, {"type": "string", "bytes": 32}],
    }
    recap_type = from_dict(test_dict)
    assert isinstance(recap_type, StructType)
    assert recap_type.type_ == "struct"
    for field in recap_type.fields:
        if isinstance(field, IntType):
            assert field.type_ == "int"
            assert field.bits == 32
        elif isinstance(field, StringType):
            assert field.type_ == "string"
            assert field.bytes_ == 32


def test_enum_type():
    test_dict = {"type": "enum", "symbols": ["RED", "GREEN", "BLUE"]}
    recap_type = from_dict(test_dict)
    assert isinstance(recap_type, EnumType)
    assert recap_type.type_ == "enum"
    assert recap_type.symbols == ["RED", "GREEN", "BLUE"]


@pytest.mark.parametrize(
    "test_dict",
    [
        {
            "type": "union",
            "types": [{"type": "int", "bits": 32}, {"type": "string", "bytes": 32}],
        },
        {
            "type": "union",
            "types": ["int32", "string32"],
        },
        {
            "type": "union",
            "types": ["int32", {"type": "string", "bytes": 32}],
        },
    ],
)
def test_union_type(test_dict):
    recap_type = from_dict(test_dict)
    assert isinstance(recap_type, UnionType)
    assert recap_type.type_ == "union"
    for type_ in recap_type.types:
        if isinstance(type_, IntType):
            assert type_.type_ == "int"
            assert type_.bits == 32
        elif isinstance(type_, StringType):
            assert type_.type_ == "string"
            assert type_.bytes_ == 32


aliases = [
    "int8",
    "uint8",
    "int16",
    "uint16",
    "int32",
    "uint32",
    "int64",
    "uint64",
    "float16",
    "float32",
    "float64",
    "string32",
    "string64",
    "bytes32",
    "bytes64",
    "uuid",
    "decimal128",
    "decimal256",
    "duration64",
    "interval128",
    "time32",
    "time64",
    "timestamp64",
    "date32",
    "date64",
]


@pytest.mark.parametrize("alias", aliases)
def test_from_dict_aliases(alias):
    recap_type_registry = RecapTypeRegistry()
    recap_type = from_dict({"type": alias}, recap_type_registry)
    assert isinstance(recap_type, ProxyType)
    assert recap_type.resolve() == recap_type_registry.from_alias(alias)


def test_from_dict_raises_for_missing_type():
    with pytest.raises(AssertionError):
        from_dict({"alias": "alias"})

def test_from_dict_unknown_type():
    unknown_type_dict = {
        "type": "unknown",
        "name": "bleh",
    }
    recap_type = from_dict(unknown_type_dict)
    assert isinstance(recap_type, UnknownType)
    assert recap_type.extra_attrs["name"] == "bleh"
    assert recap_type.description == "Unknown or unsupported type"

def test_from_dict_unknown_with_description_type():
    unknown_type_dict = {
        "type": "unknown",
        "name": "bleh",
        "description": "This is a description",
    }
    recap_type = from_dict(unknown_type_dict)
    assert isinstance(recap_type, UnknownType)
    assert recap_type.extra_attrs["name"] == "bleh"
    assert recap_type.description == "This is a description"

def test_from_dict_self_referencing_structure():
    # define the test_dict with the self-referencing structure
    test_dict = {
        "type": "struct",
        "fields": [
            {"type": "int", "bits": 32},
            {"type": "build.recap.SelfReferencingStructure"},
        ],
        "alias": "build.recap.SelfReferencingStructure",
    }

    # Create a self-referencing RecapType
    recap_type = from_dict(test_dict)
    assert isinstance(recap_type, StructType)
    assert recap_type.type_ == "struct"
    assert len(recap_type.fields) == 2
    if isinstance(recap_type.fields[0], IntType):
        assert recap_type.fields[0].type_ == "int"
        assert recap_type.fields[0].bits == 32
    elif isinstance(recap_type.fields[1], ProxyType):
        assert recap_type.fields[1].type_ == "proxy"
        assert recap_type.fields[1].alias == "build.recap.SelfReferencingStructure"
        # Resolve the ProxyType and check it equals the original RecapType
        assert recap_type.fields[1].resolve() == recap_type


def test_from_dict_alias_with_attribute_override():
    # Define a dictionary with a struct RecapType that includes a
    # self-reference with an attribute override
    test_dict = {
        "type": "struct",
        "fields": [
            {"type": "int", "bits": 32, "alias": "build.recap.MyInt"},
            {"type": "build.recap.MyInt", "signed": False},
        ],
    }

    # Create a self-referencing RecapType with attribute overrides
    recap_type = from_dict(test_dict)
    assert isinstance(recap_type, StructType)
    assert recap_type.type_ == "struct"
    for field in recap_type.fields:
        if isinstance(field, IntType):
            assert field.type_ == "int"
            assert field.bits == 32
            assert field.signed is True
        elif isinstance(field, ProxyType):
            assert field.type_ == "proxy"
            assert field.alias == "build.recap.MyInt"
            # Resolve the ProxyType and check it equals the original RecapType
            resolved_type = field.resolve()
            assert isinstance(resolved_type, IntType)
            assert resolved_type.type_ == "int"
            assert resolved_type.bits == 32
            assert resolved_type.signed is False


def test_from_dict_uuid_logical_type():
    logical_type_dict = {
        "type": "string",
        "logical": "build.recap.UUID",
        "bytes": 36,
        "variable": False,
    }
    recap_type = from_dict(logical_type_dict)
    assert isinstance(recap_type, StringType)
    assert recap_type.logical == logical_type_dict["logical"]
    assert recap_type.bytes_ == logical_type_dict["bytes"]
    assert recap_type.variable == logical_type_dict["variable"]


def test_from_dict_decimal128_logical_type():
    logical_type_dict = {
        "type": "bytes",
        "logical": "build.recap.Decimal",
        "bytes": 16,
        "variable": False,
        "precision": 28,
        "scale": 14,
    }
    recap_type = from_dict(logical_type_dict)
    assert isinstance(recap_type, BytesType)
    assert recap_type.logical == logical_type_dict["logical"]
    assert recap_type.bytes_ == logical_type_dict["bytes"]
    assert recap_type.variable == logical_type_dict["variable"]
    assert recap_type.extra_attrs["precision"] == logical_type_dict["precision"]
    assert recap_type.extra_attrs["scale"] == logical_type_dict["scale"]


def test_from_dict_duration64_logical_type():
    logical_type_dict = {
        "type": "int",
        "logical": "build.recap.Duration",
        "bits": 64,
        "signed": True,
        "unit": "millisecond",
    }
    recap_type = from_dict(logical_type_dict)
    assert isinstance(recap_type, IntType)
    assert recap_type.logical == logical_type_dict["logical"]
    assert recap_type.bits == logical_type_dict["bits"]
    assert recap_type.signed == logical_type_dict["signed"]
    assert recap_type.extra_attrs["unit"] == logical_type_dict["unit"]


def test_from_dict_time64_logical_type():
    logical_type_dict = {
        "type": "int",
        "logical": "build.recap.Time",
        "bits": 64,
        "signed": True,
        "unit": "second",
    }
    recap_type = from_dict(logical_type_dict)
    assert isinstance(recap_type, IntType)
    assert recap_type.logical == logical_type_dict["logical"]
    assert recap_type.bits == logical_type_dict["bits"]
    assert recap_type.signed == logical_type_dict["signed"]
    assert recap_type.extra_attrs["unit"] == logical_type_dict["unit"]


def test_from_dict_timestamp64_logical_type():
    logical_type_dict = {
        "type": "int",
        "logical": "build.recap.Timestamp",
        "bits": 64,
        "signed": True,
        "unit": "millisecond",
    }
    recap_type = from_dict(logical_type_dict)
    assert isinstance(recap_type, IntType)
    assert recap_type.logical == logical_type_dict["logical"]
    assert recap_type.bits == logical_type_dict["bits"]
    assert recap_type.signed == logical_type_dict["signed"]
    assert recap_type.extra_attrs["unit"] == logical_type_dict["unit"]


def test_from_dict_date64_logical_type():
    logical_type_dict = {
        "type": "int",
        "logical": "build.recap.Date",
        "bits": 64,
        "signed": True,
        "unit": "day",
    }
    recap_type = from_dict(logical_type_dict)
    assert isinstance(recap_type, IntType)
    assert recap_type.logical == logical_type_dict["logical"]
    assert recap_type.bits == logical_type_dict["bits"]
    assert recap_type.signed == logical_type_dict["signed"]
    assert recap_type.extra_attrs["unit"] == logical_type_dict["unit"]


def test_from_dict_interval_logical_type():
    logical_type_dict = {
        "type": "bytes",
        "logical": "build.recap.Interval",
        "bytes": 12,
        "variable": False,
    }
    recap_type = from_dict(logical_type_dict)
    assert isinstance(recap_type, BytesType)
    assert recap_type.logical == logical_type_dict["logical"]
    assert recap_type.bytes_ == logical_type_dict["bytes"]
    assert recap_type.variable == logical_type_dict["variable"]


def test_from_dict_complex_struct_type():
    input_dict = {
        "type": "struct",
        "fields": [
            {
                "type": "list",
                "values": {
                    "type": "map",
                    "keys": {"type": "int", "bits": 32},
                    "values": {"type": "string", "bytes": 50},
                },
            }
        ],
    }
    result = from_dict(input_dict)
    assert isinstance(result, StructType)
    assert isinstance(result.fields[0], ListType)
    assert isinstance(result.fields[0].values, MapType)
    assert isinstance(result.fields[0].values.keys, IntType)
    assert result.fields[0].values.keys.bits == 32
    assert isinstance(result.fields[0].values.values, StringType)
    assert result.fields[0].values.values.bytes_ == 50


def test_from_dict_complex_union_type():
    input_dict = {
        "type": "union",
        "types": [
            {"type": "int", "bits": 32},
            {"type": "struct", "fields": [{"type": "bool"}]},
        ],
    }
    result = from_dict(input_dict)
    assert isinstance(result, UnionType)
    assert len(result.types) == 2
    assert isinstance(result.types[0], IntType)
    assert result.types[0].bits == 32
    assert isinstance(result.types[1], StructType)
    assert isinstance(result.types[1].fields[0], BoolType)


def test_from_dict_missing_type():
    with pytest.raises(AssertionError):
        input_dict = {}
        from_dict(input_dict)


def test_from_dict_missing_required_field_for_int():
    with pytest.raises(ValueError):
        input_dict = {"type": "int"}
        from_dict(input_dict)


def test_from_dict_from_dict_with_union():
    # Define a dictionary representing a union of 'null' and a complex type
    type_dict = {
        "type": [
            "null",
            {
                "type": "map",
                "keys": {"type": "int", "bits": 32},
                "values": {"type": "string", "bytes": 4},
            },
        ]
    }

    # Call from_dict and verify the resulting RecapType
    recap_type = from_dict(type_dict)

    assert isinstance(recap_type, UnionType)
    assert len(recap_type.types) == 2
    assert isinstance(recap_type.types[0], NullType)
    assert isinstance(recap_type.types[1], MapType)
    assert isinstance(recap_type.types[1].keys, IntType)
    assert recap_type.types[1].keys.bits == 32
    assert isinstance(recap_type.types[1].values, StringType)
    assert recap_type.types[1].values.bytes_ == 4


def test_from_dict_with_union_alias():
    # Define a dictionary representing a union of 'null' and 'timestamp64'
    type_dict = {
        "type": [
            "null",
            "timestamp64",
        ]
    }

    # Call from_dict and verify the resulting RecapType
    recap_type = from_dict(type_dict)

    assert isinstance(recap_type, UnionType)
    assert len(recap_type.types) == 2
    assert isinstance(recap_type.types[0], NullType)
    assert isinstance(recap_type.types[1], ProxyType)
    assert recap_type.types[1].alias == "timestamp64"
    resolved_type = recap_type.types[1].resolve()
    assert isinstance(resolved_type, IntType)
    assert resolved_type.logical == "build.recap.Timestamp"
    assert resolved_type.bits == 64
    assert resolved_type.signed is True
    assert resolved_type.extra_attrs["unit"] == "millisecond"


def test_from_dict_struct_with_string_field_no_bytes_set():
    input_dict = {
        "type": "struct",
        "fields": [
            {
                "type": "string",
            }
        ],
    }
    result = from_dict(input_dict)
    assert isinstance(result, StructType)
    assert isinstance(result.fields[0], StringType)
    assert result.fields[0].bytes_ is None


def test_from_dict_struct_with_bytes_field_no_bytes_set():
    input_dict = {
        "type": "struct",
        "fields": [
            {
                "type": "bytes",
            }
        ],
    }
    result = from_dict(input_dict)
    assert isinstance(result, StructType)
    assert isinstance(result.fields[0], BytesType)
    assert result.fields[0].bytes_ is None


def test_from_dict_optional_field():
    # Define a dictionary with a struct RecapType that includes an optional field
    test_dict = {
        "type": "struct",
        "fields": [
            {
                "name": "field1",
                "type": "int",
                "bits": 32,
            },
            {
                "name": "field2",
                "type": "float",
                "bits": 64,
                "optional": True,
            },
        ],
    }

    # Create a RecapType from the dictionary
    recap_type = from_dict(test_dict)

    # Verify the RecapType
    assert isinstance(recap_type, StructType)
    assert recap_type.type_ == "struct"
    assert len(recap_type.fields) == 2

    # Verify the first field
    field1 = recap_type.fields[0]
    assert field1.extra_attrs["name"] == "field1"
    assert isinstance(field1, IntType)
    assert field1.type_ == "int"
    assert field1.bits == 32

    # Verify the second field
    field2 = recap_type.fields[1]
    assert field2.extra_attrs.get("name") == "field2"
    assert field2.extra_attrs["default"] is None
    assert isinstance(field2, UnionType)
    assert isinstance(field2.types[0], NullType)
    assert isinstance(field2.types[1], FloatType)
    assert field2.types[1].type_ == "float"
    assert field2.types[1].bits == 64


def test_from_dict_alias_with_default_and_doc():
    # Verify that defaults in aliases are excluded
    test_dict = {
        "type": "struct",
        "fields": [
            {
                "name": "field1",
                "alias": "build.recap.Int32",
                "doc": "This is a test",
                "type": "int",
                "bits": 32,
                "default": -1,
            },
            {
                "name": "field2",
                "type": "build.recap.Int32",
            },
        ],
    }

    # Create a RecapType from the dictionary
    recap_type = from_dict(test_dict)

    # Verify the RecapType
    assert isinstance(recap_type, StructType)
    assert recap_type.type_ == "struct"
    assert len(recap_type.fields) == 2

    # Verify the first field
    field1 = recap_type.fields[0]
    assert field1.extra_attrs["name"] == "field1"
    assert isinstance(field1, IntType)
    assert field1.alias == "build.recap.Int32"
    assert field1.type_ == "int"
    assert field1.doc == "This is a test"
    assert field1.bits == 32
    assert field1.extra_attrs.get("default") == -1

    # Verify the second field
    field2 = recap_type.fields[1]
    assert field2.extra_attrs.get("name") == "field2"
    assert field2.extra_attrs.get("default") is None
    assert isinstance(field2, ProxyType)
    resolved_type = field2.resolve()
    assert isinstance(resolved_type, IntType)
    assert resolved_type.type_ == "int"
    assert resolved_type.bits == 32
    assert resolved_type.alias is None
    assert resolved_type.doc is None
    assert resolved_type.extra_attrs.get("name") == "field2"
    assert resolved_type.extra_attrs.get("default") is None


def test_from_dict_alias_with_no_default():
    # Verify that defaults in alias references are included
    test_dict = {
        "type": "struct",
        "fields": [
            {
                "name": "field1",
                "alias": "build.recap.Int32",
                "type": "int",
                "bits": 32,
            },
            {
                "name": "field2",
                "type": "build.recap.Int32",
                "default": -1,
            },
        ],
    }

    # Create a RecapType from the dictionary
    recap_type = from_dict(test_dict)

    # Verify the RecapType
    assert isinstance(recap_type, StructType)
    assert recap_type.type_ == "struct"
    assert len(recap_type.fields) == 2

    # Verify the first field
    field1 = recap_type.fields[0]
    assert field1.extra_attrs["name"] == "field1"
    assert isinstance(field1, IntType)
    assert field1.alias == "build.recap.Int32"
    assert field1.type_ == "int"
    assert field1.bits == 32
    assert field1.extra_attrs.get("default") is None

    # Verify the second field
    field2 = recap_type.fields[1]
    assert field2.extra_attrs.get("name") == "field2"
    assert field2.extra_attrs.get("default") == -1
    assert isinstance(field2, ProxyType)
    resolved_type = field2.resolve()
    assert isinstance(resolved_type, IntType)
    assert resolved_type.type_ == "int"
    assert resolved_type.bits == 32
    assert resolved_type.alias is None
    assert resolved_type.extra_attrs.get("name") == "field2"
    assert resolved_type.extra_attrs.get("default") == -1


@pytest.mark.parametrize(
    "input_value, expected_dict, clean, alias",
    [
        (
            NullType(),
            {
                "type": "null",
                "alias": None,
                "doc": None,
                "logical": None,
            },
            False,
            False,
        ),
        (
            NullType(),
            "null",
            True,
            False,
        ),
        (
            BoolType(),
            "bool",
            True,
            False,
        ),
        (
            IntType(bits=32),
            {
                "type": "int",
                "bits": 32,
                "signed": True,
                "alias": None,
                "doc": None,
                "logical": None,
            },
            False,
            False,
        ),
        (
            IntType(bits=32),
            {"type": "int", "bits": 32},
            True,
            False,
        ),
        (
            IntType(bits=32, signed=False),
            {"type": "int", "bits": 32, "signed": False},
            True,
            False,
        ),
        (
            FloatType(bits=32),
            {"type": "float", "bits": 32},
            True,
            False,
        ),
        (
            StringType(),
            "string",
            True,
            False,
        ),
        (
            StringType(bytes_=50),
            {"type": "string", "bytes": 50},
            True,
            False,
        ),
        (
            BytesType(),
            "bytes",
            True,
            False,
        ),
        (
            BytesType(bytes_=50),
            {"type": "bytes", "bytes": 50},
            True,
            False,
        ),
        (
            EnumType(symbols=["foo", "bar"]),
            {"type": "enum", "symbols": ["foo", "bar"]},
            True,
            False,
        ),
        (
            ListType(values=IntType(bits=32)),
            {"type": "list", "values": {"type": "int", "bits": 32}},
            True,
            False,
        ),
        (
            ListType(
                values=IntType(bits=32),
                length=10,
            ),
            {
                "type": "list",
                "values": {"type": "int", "bits": 32},
                "length": 10,
            },
            True,
            False,
        ),
        (
            MapType(
                keys=IntType(bits=32),
                values=StringType(bytes_=50),
            ),
            {
                "type": "map",
                "keys": {"type": "int", "bits": 32},
                "values": {"type": "string", "bytes": 50},
            },
            True,
            False,
        ),
        (
            UnionType(
                types=[
                    IntType(bits=32),
                    StringType(bytes_=50),
                ]
            ),
            [
                {"type": "int", "bits": 32},
                {"type": "string", "bytes": 50},
            ],
            True,
            False,
        ),
        (
            StructType(
                fields=[
                    IntType(bits=32),
                    StringType(bytes_=50),
                ]
            ),
            {
                "type": "struct",
                "fields": [
                    {"type": "int", "bits": 32},
                    {"type": "string", "bytes": 50},
                ],
            },
            True,
            False,
        ),
        (
            StructType(
                fields=[
                    UnionType(
                        default=None,
                        types=[
                            NullType(),
                            IntType(bits=32),
                            StringType(bytes_=50),
                        ],
                    )
                ]
            ),
            {
                "type": "struct",
                "fields": [
                    {
                        "type": "union",
                        "types": [
                            {"type": "int", "bits": 32},
                            {"type": "string", "bytes": 50},
                        ],
                        "optional": True,
                    }
                ],
            },
            True,
            False,
        ),
        (
            StructType(
                fields=[
                    ListType(
                        values=MapType(
                            keys=IntType(bits=32), values=StringType(bytes_=50)
                        )
                    )
                ]
            ),
            {
                "type": "struct",
                "fields": [
                    {
                        "type": "list",
                        "values": {
                            "type": "map",
                            "keys": {"type": "int", "bits": 32},
                            "values": {"type": "string", "bytes": 50},
                        },
                    }
                ],
            },
            True,
            False,
        ),
        (
            ProxyType("test_proxy", RecapTypeRegistry()),
            "test_proxy",
            True,
            False,
        ),
        (
            IntType(bits=32),
            "int32",
            True,
            True,
        ),
        (
            BytesType(
                logical="build.recap.Decimal",
                bytes_=32,
                variable=False,
                precision=56,
                scale=28,
            ),
            "decimal256",
            True,
            True,
        ),
        (
            StructType(
                fields=[
                    StringType(
                        name="foo",
                        bytes_=10,
                        variable=False,
                        default="bar",
                    ),
                ],
            ),
            {
                "type": "struct",
                "fields": [
                    {
                        "type": "string",
                        "bytes": 10,
                        "variable": False,
                        "default": "bar",
                        "name": "foo",
                    },
                ],
            },
            True,
            True,
        ),
        (
            StructType(
                fields=[
                    UnionType(
                        types=[
                            NullType(),
                            StringType(bytes_=50),
                            IntType(bits=32),
                        ],
                        default=None,
                    ),
                ],
            ),
            {
                "type": "struct",
                "fields": [
                    {
                        "type": "union",
                        "types": [
                            {"type": "string", "bytes": 50},
                            {"type": "int", "bits": 32},
                        ],
                        "optional": True,
                    }
                ],
            },
            True,
            False,
        ),
        (
            StructType(
                fields=[
                    UnionType(
                        types=[
                            NullType(),
                            StringType(bytes_=50),
                            IntType(bits=32),
                        ],
                        default="some_string",
                    ),
                ],
            ),
            {
                "type": "struct",
                "fields": [
                    {
                        "type": "union",
                        "types": [
                            {"type": "string", "bytes": 50},
                            {"type": "int", "bits": 32},
                        ],
                        "optional": True,
                        "default": "some_string",
                    }
                ],
            },
            True,
            False,
        ),
        (
            StructType(
                fields=[
                    UnionType(
                        types=[
                            NullType(),
                            StringType(bytes_=50),
                            IntType(bits=32),
                        ],
                        default=None,
                    ),
                ],
            ),
            {
                "type": "struct",
                "fields": [
                    {
                        "type": "union",
                        "types": [
                            {"type": "string", "bytes": 50},
                            "int32",
                        ],
                        "optional": True,
                    }
                ],
            },
            True,
            True,
        ),
        (
            StructType(
                fields=[
                    UnionType(
                        types=[
                            NullType(),
                            IntType(bits=32),
                        ],
                    ),
                ],
            ),
            {
                "type": "struct",
                "fields": [
                    # Union syntactic sugar
                    [
                        "null",
                        "int32",
                    ],
                ],
            },
            True,
            True,
        ),
        (
            StructType(
                fields=[
                    UnionType(
                        types=[
                            NullType(),
                            StringType(bytes_=50),
                            IntType(bits=32),
                        ],
                        default=None,
                        alias="recap.build.TestUnion",
                    ),
                ],
            ),
            {
                "type": "struct",
                "fields": [
                    {
                        "type": "union",
                        "alias": "recap.build.TestUnion",
                        "types": [
                            {"type": "string", "bytes": 50},
                            "int32",
                        ],
                        "optional": True,
                    }
                ],
            },
            True,
            True,
        ),
        (
            StructType(
                fields=[
                    StringType(
                        name="primary_phone",
                        alias="build.recap.Phone",
                        bytes_=10,
                    ),
                    UnionType(
                        name="secondary_phone",
                        types=[
                            NullType(),
                            ProxyType(
                                alias="build.recap.Phone",
                                registry=RecapTypeRegistry(),
                            ),
                        ],
                        default=None,
                    ),
                ],
            ),
            {
                "type": "struct",
                "fields": [
                    {
                        "type": "string",
                        "bytes": 10,
                        "name": "primary_phone",
                        "alias": "build.recap.Phone",
                    },
                    {
                        "type": "build.recap.Phone",
                        "name": "secondary_phone",
                        "optional": True,
                    },
                ],
            },
            True,
            True,
        ),
    ],
)
def test_to_dict(
    input_value: RecapType,
    expected_dict: dict,
    clean: bool,
    alias: bool,
) -> None:
    assert to_dict(input_value, clean, alias) == expected_dict


@pytest.mark.parametrize(
    "input_value, clean, alias",
    [
        (
            NullType(),
            False,
            False,
        ),
        (
            NullType(),
            True,
            False,
        ),
        (
            BoolType(),
            True,
            False,
        ),
        (
            IntType(bits=32),
            False,
            False,
        ),
        (
            IntType(bits=32),
            True,
            False,
        ),
        (
            IntType(bits=32, signed=False),
            True,
            False,
        ),
        (
            FloatType(bits=32),
            True,
            False,
        ),
        (
            StringType(),
            True,
            False,
        ),
        (
            StringType(bytes_=50),
            True,
            False,
        ),
        (
            BytesType(),
            True,
            False,
        ),
        (
            BytesType(bytes_=50),
            True,
            False,
        ),
        (
            EnumType(symbols=["foo", "bar"]),
            True,
            False,
        ),
        (
            ListType(values=IntType(bits=32)),
            True,
            False,
        ),
        (
            ListType(
                values=IntType(bits=32),
                length=10,
            ),
            True,
            False,
        ),
        (
            MapType(
                keys=IntType(bits=32),
                values=StringType(bytes_=50),
            ),
            True,
            False,
        ),
        (
            UnionType(
                types=[
                    IntType(bits=32),
                    StringType(bytes_=50),
                ]
            ),
            True,
            False,
        ),
        (
            StructType(
                fields=[
                    IntType(bits=32),
                    StringType(bytes_=50),
                ]
            ),
            True,
            False,
        ),
        (
            StructType(
                fields=[
                    UnionType(
                        default=None,
                        types=[
                            NullType(),
                            IntType(bits=32),
                            StringType(bytes_=50),
                        ],
                    )
                ]
            ),
            True,
            False,
        ),
        (
            StructType(
                fields=[
                    ListType(
                        values=MapType(
                            keys=IntType(bits=32), values=StringType(bytes_=50)
                        )
                    )
                ]
            ),
            True,
            False,
        ),
        (
            ProxyType("test_proxy", RecapTypeRegistry()),
            True,
            False,
        ),
        (
            ProxyType("test_proxy", RecapTypeRegistry()),
            True,
            True,
        ),
        (
            IntType(bits=32),
            True,
            False,
        ),
        (
            BytesType(
                logical="build.recap.Decimal",
                bytes_=32,
                variable=False,
                precision=56,
                scale=28,
            ),
            True,
            False,
        ),
        (
            StructType(
                fields=[
                    StringType(
                        name="foo",
                        bytes_=10,
                        variable=False,
                        default="bar",
                    ),
                ],
            ),
            True,
            False,
        ),
    ],
)
def test_to_from_dict(
    input_value: RecapType,
    clean: bool,
    alias: bool,
):
    assert from_dict(to_dict(input_value, clean, alias)) == input_value


@pytest.mark.parametrize(
    "input_value, clean, alias",
    [
        (
            {
                "type": "null",
                "alias": None,
                "doc": None,
                "logical": None,
            },
            False,
            False,
        ),
        ("null", True, False),
        ("bool", True, False),
        (
            {
                "type": "int",
                "bits": 32,
                "signed": True,
                "alias": None,
                "doc": None,
                "logical": None,
            },
            False,
            False,
        ),
        ({"type": "int", "bits": 32}, True, False),
        ({"type": "int", "bits": 32, "signed": False}, True, False),
        ({"type": "float", "bits": 32}, True, False),
        ("string", True, False),
        ({"type": "string", "bytes": 50}, True, False),
        ("bytes", True, False),
        ({"type": "bytes", "bytes": 50}, True, False),
        ({"type": "enum", "symbols": ["foo", "bar"]}, True, False),
        ({"type": "list", "values": {"type": "int", "bits": 32}}, True, False),
        (
            {
                "type": "list",
                "values": {"type": "int", "bits": 32},
                "length": 10,
            },
            True,
            False,
        ),
        (
            {
                "type": "map",
                "keys": {"type": "int", "bits": 32},
                "values": {"type": "string", "bytes": 50},
            },
            True,
            False,
        ),
        (
            [
                {"type": "int", "bits": 32},
                {"type": "string", "bytes": 50},
            ],
            True,
            False,
        ),
        (
            {
                "type": "struct",
                "fields": [
                    {"type": "int", "bits": 32},
                    {"type": "string", "bytes": 50},
                ],
            },
            True,
            False,
        ),
        (
            {
                "type": "struct",
                "fields": [
                    {
                        "type": "union",
                        "types": [
                            {"type": "int", "bits": 32},
                            {"type": "string", "bytes": 50},
                        ],
                        "optional": True,
                    }
                ],
            },
            True,
            False,
        ),
        (
            {
                "type": "struct",
                "fields": [
                    {
                        "type": "list",
                        "values": {
                            "type": "map",
                            "keys": {"type": "int", "bits": 32},
                            "values": {"type": "string", "bytes": 50},
                        },
                    }
                ],
            },
            True,
            False,
        ),
        ("test_proxy", True, True),
        ("test_proxy", True, False),
        ("int32", True, True),
        ("int32", True, False),
        ("decimal256", True, True),
        ("decimal256", True, False),
        (
            {
                "type": "struct",
                "fields": [
                    {
                        "type": "string",
                        "bytes": 10,
                        "variable": False,
                        "default": "bar",
                        "name": "foo",
                    },
                ],
            },
            True,
            True,
        ),
    ],
)
def test_from_to_dict(
    input_value: dict,
    clean: bool,
    alias: bool,
) -> None:
    assert to_dict(from_dict(input_value), clean, alias) == input_value


def test_to_dict_compact_union():
    union_type = UnionType(
        types=[
            IntType(bits=30),
            StringType(bytes_=50),
        ]
    )
    assert to_dict(union_type) == [
        {"type": "int", "bits": 30},
        {"type": "string", "bytes": 50},
    ]


def test_to_dict_compact_type():
    assert to_dict(IntType(bits=32)) == "int32"


@pytest.mark.parametrize(
    "test_input, expected",
    [
        # Valid cases
        ("foo.bar.Baz", True),
        ("foo.Baz", True),
        ("foo123_.blah", True),
        ("_foo.blah", True),
        ("bar123___.___b123lah___43", True),
        ("foo.bar.baz.blah", True),
        # Invalid cases
        ("foo", False),
        ("123foo", False),
        ("123.blah", False),
        ("123blah.blah", False),
        ("blah.123blah", False),
        (".blah", False),
        ("blah.", False),
        ("foo..blah", False),
        ("foo.blah.", False),
    ],
)
def test_alias_regex(test_input, expected):
    assert (re.fullmatch(ALIAS_REGEX, test_input) is not None) == expected


@pytest.mark.parametrize(
    "recap_type",
    [
        # Valid cases
        pytest.param(BoolType(alias="foo.bar.Baz"), id="valid:foo.bar.Baz"),
        pytest.param(BoolType(alias="foo.Baz"), id="valid:foo.Baz"),
        pytest.param(BoolType(alias="foo123_.blah"), id="valid:foo123_.blah"),
        pytest.param(BoolType(alias="foo_.blah123"), id="valid:foo_.blah123"),
        pytest.param(BoolType(alias="_foo.blah"), id="valid:_foo.blah"),
        pytest.param(
            BoolType(alias="bar123___.___b123lah___43"),
            id="valid:bar123___.___b123lah___43",
        ),
        # Invalid cases
        pytest.param(
            BoolType(alias="foo"),
            id="invalid:foo",
            marks=pytest.mark.xfail,
        ),
        pytest.param(
            BoolType(alias="123foo"),
            id="invalid:123foo",
            marks=pytest.mark.xfail,
        ),
        pytest.param(
            BoolType(alias=".blah"),
            id="invalid:.blah",
            marks=pytest.mark.xfail,
        ),
        pytest.param(
            BoolType(alias="blah."),
            id="invalid:blah.",
            marks=pytest.mark.xfail,
        ),
        pytest.param(
            BoolType(alias="foo..blah"),
            id="invalid:foo..blah",
            marks=pytest.mark.xfail,
        ),
        pytest.param(
            BoolType(alias="foo.blah."),
            id="invalid:foo..blah",
            marks=pytest.mark.xfail,
        ),
        pytest.param(
            BoolType(alias=""),
            id="invalid:foo..blah",
            marks=pytest.mark.xfail,
        ),
        pytest.param(
            BoolType(alias=" foo.Baz"),
            id="valid:foo.Baz",
            marks=pytest.mark.xfail,
        ),
        pytest.param(
            BoolType(alias="foo.Baz "),
            id="valid:foo.Baz",
            marks=pytest.mark.xfail,
        ),
    ],
)
def test_register_alias(recap_type):
    registry = RecapTypeRegistry()
    registry.register_alias(recap_type)


def test_int_type_validate():
    invalid_int1 = IntType(-1)
    invalid_int2 = IntType(2_147_483_648)

    with pytest.raises(ValueError):
        invalid_int1.validate()
    with pytest.raises(ValueError):
        invalid_int2.validate()


def test_float_type_validate():
    invalid_float1 = FloatType(-1)
    invalid_float2 = FloatType(2_147_483_648)

    with pytest.raises(ValueError):
        invalid_float1.validate()
    with pytest.raises(ValueError):
        invalid_float2.validate()


def test_string_type_validate():
    invalid_string1 = StringType(-1)
    invalid_string2 = StringType(9_223_372_036_854_775_808)

    with pytest.raises(ValueError):
        invalid_string1.validate()
    with pytest.raises(ValueError):
        invalid_string2.validate()


def test_bytes_type_validate():
    invalid_bytes1 = BytesType(-1)
    invalid_bytes2 = BytesType(9_223_372_036_854_775_808)

    with pytest.raises(ValueError):
        invalid_bytes1.validate()
    with pytest.raises(ValueError):
        invalid_bytes2.validate()


def test_list_type_validate():
    invalid_list1 = ListType(StringType(65_536), length=-1)
    invalid_list2 = ListType(StringType(65_536), variable=False)
    invalid_list3 = ListType(StringType(), length=9_223_372_036_854_775_808)

    with pytest.raises(ValueError):
        invalid_list1.validate()
    with pytest.raises(ValueError):
        invalid_list2.validate()
    with pytest.raises(ValueError):
        invalid_list3.validate()


def test_map_type_validate():
    invalid_map_keys = MapType(
        StringType(bytes_=9_223_372_036_854_775_808), IntType(32)
    )
    invalid_map_values = MapType(StringType(65_536), IntType(2_147_483_648))

    with pytest.raises(ValueError):
        invalid_map_keys.validate()
    with pytest.raises(ValueError):
        invalid_map_values.validate()


def test_struct_type_validate():
    invalid_struct = StructType([StringType(65_536), IntType(2_147_483_648)])

    with pytest.raises(ValueError):
        invalid_struct.validate()


def test_make_nullable_of_union():
    union_type = UnionType(
        types=[
            IntType(bits=32),
            StringType(bytes_=50),
        ]
    )
    assert union_type.make_nullable() == UnionType(
        types=[
            NullType(),
            IntType(bits=32),
            StringType(bytes_=50),
        ],
        default=None,
        doc=None,
    )


def test_make_nullable_of_nullable():
    union_type = UnionType(
        types=[
            NullType(),
            IntType(bits=32),
        ],
        default=None,
    )
    assert union_type.make_nullable() == UnionType(
        types=[
            NullType(),
            IntType(bits=32),
        ],
        default=None,
    )


def test_make_nullable_of_default_none():
    union_type = NullType(default=None)
    assert union_type.make_nullable() == UnionType(
        types=[
            NullType(),
        ],
        default=None,
    )


def test_is_nullable():
    assert NullType().is_nullable() is True
    assert NullType(doc="Something", foo=123).is_nullable() is True
    assert IntType(bits=32).is_nullable() is False
    assert (
        UnionType(
            types=[
                NullType(),
                IntType(bits=32),
            ],
            default=None,
        ).is_nullable()
        is True
    )
    assert (
        UnionType(
            types=[
                IntType(bits=32),
                NullType(doc="Something", foo=123),
            ],
            default=123,
        ).is_nullable()
        is True
    )
    assert (
        UnionType(
            types=[
                IntType(bits=32),
                StringType(bytes_=50),
            ],
            default=123,
        ).is_nullable()
        is False
    )
