from json import loads

import pytest
from jsonschema.validators import Draft202012Validator

from recap.converters.json_schema import JSONSchemaConverter
from recap.types import (
    BoolType,
    BytesType,
    EnumType,
    FloatType,
    IntType,
    ListType,
    MapType,
    NullType,
    ProxyType,
    StringType,
    StructType,
    UnionType,
    UnknownType,
)


def test_all_basic_types():
    json_schema = """
    {
        "type": "object",
        "properties": {
            "a_string": {"type": "string"},
            "a_number": {"type": "number"},
            "an_integer": {"type": "integer"},
            "a_boolean": {"type": "boolean"},
            "a_null": {"type": "null"}
        }
    }
    """
    Draft202012Validator.check_schema(loads(json_schema))
    struct_type = JSONSchemaConverter().to_recap(json_schema)
    assert isinstance(struct_type, StructType)
    assert struct_type.fields == [
        UnionType(
            [NullType(), StringType()],
            default=None,
            name="a_string",
        ),
        UnionType(
            [NullType(), FloatType(bits=64)],
            default=None,
            name="a_number",
        ),
        UnionType(
            [NullType(), IntType(bits=32, signed=True)],
            default=None,
            name="an_integer",
        ),
        UnionType(
            [NullType(), BoolType()],
            default=None,
            name="a_boolean",
        ),
        NullType(default=None, name="a_null"),
    ]


def test_nullable_types():
    """Tests nullable types (["null", "string"]), with and without default values. Also tests that nullable properties aren't
    made double nullable if they're not required."""
    json_schema = """
    {
        "type": "object",
        "properties": {
            "required_nullable_no_default":  {"type": ["null", "string"]},
            "required_nullable_with_null_default":  {"type": ["null", "string"], "default": null},
            "required_nullable_with_default":  {"type": ["null", "string"], "default": "default_value"},
            "nullable_no_default":  {"type": ["null", "string"]},
            "nullable_with_null_default":  {"type": ["null", "string"], "default": null},
            "nullable_with_default":  {"type": ["null", "string"], "default": "default_value"}
        },
        "required": ["required_nullable_no_default", "required_nullable_with_null_default", "required_nullable_with_default"]
    }
    """
    Draft202012Validator.check_schema(loads(json_schema))
    struct_type = JSONSchemaConverter().to_recap(json_schema)
    assert isinstance(struct_type, StructType)
    assert struct_type.fields == [
        UnionType([NullType(), StringType()], name="required_nullable_no_default"),
        UnionType(
            [NullType(), StringType()],
            name="required_nullable_with_null_default",
            default=None,
        ),
        UnionType(
            [NullType(), StringType()],
            name="required_nullable_with_default",
            default="default_value",
        ),
        UnionType([NullType(), StringType()], name="nullable_no_default", default=None),
        UnionType(
            [NullType(), StringType()],
            name="nullable_with_null_default",
            default=None,
        ),
        UnionType(
            [NullType(), StringType()],
            name="nullable_with_default",
            default="default_value",
        ),
    ]


def test_union_types():
    json_schema = """
    {
        "type": "object",
        "properties": {
            "union":  {"type": ["null", "string", "boolean", "number"]}
        },
        "required": ["union"]
    }
    """
    Draft202012Validator.check_schema(loads(json_schema))
    struct_type = JSONSchemaConverter().to_recap(json_schema)
    assert isinstance(struct_type, StructType)
    assert struct_type.fields == [
        UnionType(
            [NullType(), StringType(), BoolType(), FloatType(bits=64)], name="union"
        ),
    ]


def test_nested_objects():
    json_schema = """
    {
        "type": "object",
        "properties": {
            "an_object": {
                "type": "object",
                "properties": {
                    "a_string": {"type": "string"}
                }
            }
        }
    }
    """
    Draft202012Validator.check_schema(loads(json_schema))
    struct_type = JSONSchemaConverter().to_recap(json_schema)
    assert isinstance(struct_type, StructType)
    assert struct_type.fields == [
        UnionType(
            [
                NullType(),
                StructType(
                    [
                        UnionType(
                            [NullType(), StringType()],
                            name="a_string",
                            default=None,
                        ),
                    ],
                ),
            ],
            name="an_object",
            default=None,
        ),
    ]


def test_object_with_array_of_objects():
    json_schema = """
    {
        "type": "object",
        "properties": {
            "an_array": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "a_string": {"type": "string"}
                    }
                }
            }
        }
    }
    """
    Draft202012Validator.check_schema(loads(json_schema))
    struct_type = JSONSchemaConverter().to_recap(json_schema)
    assert isinstance(struct_type, StructType)
    assert struct_type.fields == [
        UnionType(
            [
                NullType(),
                ListType(
                    StructType(
                        [
                            UnionType(
                                [
                                    NullType(),
                                    StringType(),
                                ],
                                name="a_string",
                                default=None,
                            )
                        ]
                    ),
                ),
            ],
            name="an_array",
            default=None,
        ),
    ]


def test_required_properties():
    json_schema = """
    {
        "type": "object",
        "properties": {
            "required_property": {"type": "string"},
            "optional_property": {"type": "number"}
        },
        "required": ["required_property"]
    }
    """
    Draft202012Validator.check_schema(loads(json_schema))
    struct_type = JSONSchemaConverter().to_recap(json_schema)
    assert isinstance(struct_type, StructType)
    assert struct_type.fields == [
        StringType(name="required_property"),
        UnionType(
            [NullType(), FloatType(bits=64)],
            name="optional_property",
            default=None,
        ),
    ]


def test_doc_attribute():
    json_schema = """
    {
        "type": "object",
        "properties": {
            "a_string": {
                "type": "string",
                "description": "This is a string"
            }
        }
    }
    """
    Draft202012Validator.check_schema(loads(json_schema))
    struct_type = JSONSchemaConverter().to_recap(json_schema)
    assert isinstance(struct_type, StructType)
    assert struct_type.fields == [
        UnionType(
            [NullType(), StringType()],
            name="a_string",
            doc="This is a string",
            default=None,
        ),
    ]


def test_name_attribute():
    json_schema = """
    {
        "type": "object",
        "properties": {
            "a_string": {
                "type": "string",
                "title": "A String"
            }
        }
    }
    """
    Draft202012Validator.check_schema(loads(json_schema))
    struct_type = JSONSchemaConverter().to_recap(json_schema)
    assert isinstance(struct_type, StructType)
    assert struct_type.fields == [
        UnionType(
            [NullType(), StringType()],
            name="a_string",
            default=None,
        ),
    ]


def test_default_attribute():
    json_schema = """
    {
        "type": "object",
        "properties": {
            "a_string": {
                "type": "string",
                "default": "Default value"
            }
        }
    }
    """
    Draft202012Validator.check_schema(loads(json_schema))
    struct_type = JSONSchemaConverter().to_recap(json_schema)
    assert isinstance(struct_type, StructType)
    assert struct_type.fields == [
        UnionType(
            [
                NullType(),
                StringType(),
            ],
            name="a_string",
            default="Default value",
        ),
    ]


def test_convert_bytes():
    schema = """
    {
        "type": "object",
        "properties": {
            "img": {
                "type": "string",
                "format": "bytes"
            }
        }
    }
    """
    Draft202012Validator.check_schema(loads(schema))
    result = JSONSchemaConverter().to_recap(schema)
    assert result == StructType(
        [
            UnionType(
                [NullType(), BytesType()],
                name="img",
                default=None,
            ),
        ]
    )


def test_convert_date():
    converter = JSONSchemaConverter()
    schema = """
    {
        "type": "object",
        "properties": {
            "date": {
                "type": "string",
                "format": "date"
            }
        },
        "required": ["date"]
    }
    """
    Draft202012Validator.check_schema(loads(schema))
    result = converter.to_recap(schema)
    assert isinstance(result, StructType)
    assert isinstance(result.fields[0], StringType)
    assert result.fields[0].logical == "org.iso.8601.Date"


def test_convert_datetime():
    converter = JSONSchemaConverter()
    schema = """
    {
        "type": "object",
        "properties": {
            "datetime": {
                "type": "string",
                "format": "date-time"
            }
        },
        "required": ["datetime"]
    }
    """
    Draft202012Validator.check_schema(loads(schema))
    result = converter.to_recap(schema)
    assert isinstance(result, StructType)
    assert isinstance(result.fields[0], StringType)
    assert result.fields[0].logical == "org.iso.8601.DateTime"


def test_convert_time():
    converter = JSONSchemaConverter()
    schema = """
    {
        "type": "object",
        "properties": {
            "time": {
                "type": "string",
                "format": "time"
            }
        },
        "required": ["time"]
    }
    """
    Draft202012Validator.check_schema(loads(schema))
    result = converter.to_recap(schema)
    assert isinstance(result, StructType)
    assert isinstance(result.fields[0], StringType)
    assert result.fields[0].logical == "org.iso.8601.Time"


def test_id_to_recap_alias():
    json_schema_str = """
    {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": "http://example.com/path/to/schema",
        "type": "object",
        "properties": {
            "field": {
                "type": "string"
            }
        }
    }
    """
    Draft202012Validator.check_schema(loads(json_schema_str))
    recap_type = JSONSchemaConverter().to_recap(json_schema_str)
    assert recap_type == StructType(
        fields=[
            UnionType(
                [NullType(), StringType()],
                name="field",
                default=None,
            )
        ],
        alias="com.example.path.to.schema",
    )


def test_id_to_recap_alias_schema_default():
    json_schema_str = """
    {
        "$id": "http://example.com/path/to/schema",
        "type": "object",
        "properties": {
            "field": {
                "type": "string"
            }
        }
    }
    """
    Draft202012Validator.check_schema(loads(json_schema_str))
    recap_type = JSONSchemaConverter().to_recap(json_schema_str)
    assert recap_type == StructType(
        fields=[
            UnionType(
                [NullType(), StringType()],
                name="field",
                default=None,
            )
        ],
        alias="com.example.path.to.schema",
    )


def test_cyclic_reference():
    json_schema_str = """
    {
        "$id": "http://recap.build/linkedlist.schema.json",
        "description": "A node in a linked list",
        "type": "object",
        "properties": {
            "value": {
                "description": "Value of the node",
                "type": "integer"
            },
            "next": {
                "description": "Next node in the linked list",
                "$ref": "http://recap.build/linkedlist.schema.json"
            }
        },
        "required": ["value"]
    }
    """
    Draft202012Validator.check_schema(loads(json_schema_str))
    converter = JSONSchemaConverter()
    recap_type = converter.to_recap(json_schema_str)
    assert recap_type == StructType(
        fields=[
            IntType(
                name="value",
                doc="Value of the node",
                bits=32,
            ),
            UnionType(
                [
                    NullType(),
                    ProxyType(
                        alias="build.recap.linkedlist.schema.json",
                        registry=converter.registry,
                    ),
                ],
                doc="Next node in the linked list",
                name="next",
                default=None,
            ),
        ],
        alias="build.recap.linkedlist.schema.json",
        doc="A node in a linked list",
    )


def test_cyclic_reference_dynamic():
    json_schema_str = """
    {
        "$id": "http://recap.build/linkedlist.schema.json",
        "description": "A node in a linked list",
        "type": "object",
        "properties": {
            "value": {
                "description": "Value of the node",
                "type": "integer"
            },
            "next": {
                "description": "Next node in the linked list",
                "$ref": "http://recap.build/linkedlist.schema.json"
            }
        },
        "required": ["value"]
    }
    """
    Draft202012Validator.check_schema(loads(json_schema_str))
    converter = JSONSchemaConverter()
    recap_type = converter.to_recap(json_schema_str)
    assert recap_type == StructType(
        fields=[
            IntType(
                name="value",
                doc="Value of the node",
                bits=32,
            ),
            UnionType(
                [
                    NullType(),
                    ProxyType(
                        alias="build.recap.linkedlist.schema.json",
                        registry=converter.registry,
                    ),
                ],
                doc="Next node in the linked list",
                name="next",
                default=None,
            ),
        ],
        alias="build.recap.linkedlist.schema.json",
        doc="A node in a linked list",
    )


@pytest.mark.xfail(reason="Defs aren't currently implemented")
def test_defs_reference():
    json_schema_str = """
    {
        "type": "object",
        "$id": "http://recap.build/linkedlist.schema.json",
        "properties": {
            "defRef": { "$ref": "#/$defs/positiveInteger" }
        },
        "$defs": {
            "positiveInteger": {
                "type": "integer"
            }
        },
        "required": ["defRef"]
    }
    """
    Draft202012Validator.check_schema(loads(json_schema_str))
    converter = JSONSchemaConverter()
    recap_type = converter.to_recap(json_schema_str)
    assert recap_type == StructType(
        fields=[
            ProxyType(
                alias="build.recap.linkedlist.schema.json",
                registry=converter.registry,
                name="defRef",
            ),
        ],
        alias="build.recap.linkedlist.schema.json",
    )


def test_from_recap_types():
    struct = StructType(
        [
            IntType(bits=32, name="int_field"),
            StringType(name="string_field"),
            BytesType(name="bytes_field"),
            FloatType(bits=64, name="float_field"),
            BoolType(name="bool_field"),
            NullType(name="null_field"),
            ListType(values=IntType(bits=32), name="list_field"),
            MapType(keys=StringType(), values=IntType(bits=32), name="map_field"),
            EnumType(symbols=["A", "B", "C"], name="enum_field"),
            StructType(
                fields=[IntType(bits=32, name="nested_int_field")],
                name="nested_struct_field",
            ),
        ]
    )

    schema = JSONSchemaConverter().from_recap(struct)
    expected_schema = {
        "type": "object",
        "properties": {
            "int_field": {"type": "integer"},
            "string_field": {"type": "string"},
            "bytes_field": {"type": "string", "format": "byte"},
            "float_field": {"type": "number"},
            "bool_field": {"type": "boolean"},
            "null_field": {"type": "null"},
            "list_field": {"type": "array", "items": {"type": "integer"}},
            "map_field": {
                "type": "object",
                "additionalProperties": {"type": "integer"},
            },
            "enum_field": {"type": "string", "enum": ["A", "B", "C"]},
            "nested_struct_field": {
                "type": "object",
                "properties": {
                    "nested_int_field": {"type": "integer"},
                },
                "required": ["nested_int_field"],
            },
        },
        "required": [
            "int_field",
            "string_field",
            "bytes_field",
            "float_field",
            "bool_field",
            "null_field",
            "list_field",
            "map_field",
            "enum_field",
            "nested_struct_field",
        ],
    }

    Draft202012Validator.check_schema(expected_schema)
    assert schema == expected_schema


def test_from_recap_optional_types():
    struct = StructType(
        [
            UnionType(
                [NullType(), IntType(bits=32)],
                name="optional_int_field",
                default=0,
            ),
            UnionType(
                [NullType(), StringType()],
                name="optional_string_field",
                default="",
            ),
            UnionType(
                [NullType(), BytesType()],
                name="optional_bytes_field",
                default=b"",
            ),
            UnionType(
                [NullType(), FloatType(bits=64)],
                name="optional_float_field",
                default=0.0,
            ),
            UnionType(
                [NullType(), BoolType()],
                name="optional_bool_field",
                default=False,
            ),
            UnionType(
                [NullType(), ListType(values=IntType(bits=32))],
                name="optional_list_field",
                default=[],
            ),
            UnionType(
                [NullType(), MapType(keys=StringType(), values=IntType(bits=32))],
                name="optional_map_field",
                default={},
            ),
            UnionType(
                [NullType(), EnumType(symbols=["A", "B", "C"])],
                name="optional_enum_field",
                default="A",
            ),
            UnionType(
                [
                    NullType(),
                    StructType(
                        fields=[
                            UnionType(
                                [
                                    NullType(),
                                    IntType(bits=32),
                                ],
                                default=None,
                                name="nested_optional_int_field",
                            )
                        ],
                        name="struct",
                    ),
                ],
                name="optional_nested_struct_field",
                default={"nested_optional_int_field": 0},
            ),
        ]
    )

    schema = JSONSchemaConverter().from_recap(struct)
    expected_schema = {
        "type": "object",
        "properties": {
            "optional_int_field": {"type": "integer", "default": 0},
            "optional_string_field": {"type": "string", "default": ""},
            "optional_bytes_field": {
                "type": "string",
                "format": "byte",
                "default": b"",
            },
            "optional_float_field": {"type": "number", "default": 0.0},
            "optional_bool_field": {"type": "boolean", "default": False},
            "optional_list_field": {
                "type": "array",
                "items": {"type": "integer"},
                "default": [],
            },
            "optional_map_field": {
                "type": "object",
                "additionalProperties": {"type": "integer"},
                "default": {},
            },
            "optional_enum_field": {
                "type": "string",
                "enum": ["A", "B", "C"],
                "default": "A",
            },
            "optional_nested_struct_field": {
                "type": "object",
                "properties": {
                    "nested_optional_int_field": {"type": "integer", "default": None},
                },
                "default": {"nested_optional_int_field": 0},
            },
        },
    }

    Draft202012Validator.check_schema(expected_schema)
    assert schema == expected_schema


def test_from_recap_types_with_aliases():
    struct = StructType(
        [
            IntType(bits=32, name="int_field", alias="build.recap.MyInt"),
            StringType(name="string_field", alias="build.recap.MyString"),
            BytesType(name="bytes_field", alias="build.recap.MyBytes"),
            FloatType(bits=64, name="float_field", alias="build.recap.MyFloat"),
            BoolType(name="bool_field", alias="build.recap.MyBool"),
            NullType(name="null_field", alias="build.recap.MyNull"),
            ListType(
                values=IntType(bits=32, alias="build.recap.ListItem"),
                name="list_field",
                alias="build.recap.MyList",
            ),
            MapType(
                keys=StringType(alias="build.recap.MapKey"),
                values=IntType(bits=32, alias="build.recap.MapValue"),
                name="map_field",
                alias="build.recap.MyMap",
            ),
            EnumType(
                symbols=["A", "B", "C"], name="enum_field", alias="build.recap.MyEnum"
            ),
            StructType(
                fields=[
                    IntType(
                        bits=32, name="nested_int_field", alias="build.recap.NestedInt"
                    )
                ],
                name="nested_struct_field",
                alias="build.recap.NestedStruct",
            ),
        ]
    )

    schema = JSONSchemaConverter().from_recap(struct)

    expected_schema = {
        "$defs": {
            "build.recap.MyInt": {"type": "integer"},
            "build.recap.MyString": {"type": "string"},
            "build.recap.MyBytes": {"type": "string", "format": "byte"},
            "build.recap.MyFloat": {"type": "number"},
            "build.recap.MyBool": {"type": "boolean"},
            "build.recap.MyNull": {"type": "null"},
            "build.recap.ListItem": {"type": "integer"},
            "build.recap.MyList": {
                "type": "array",
                "items": {"$ref": "#/$defs/build.recap.ListItem"},
            },
            "build.recap.MapValue": {"type": "integer"},
            "build.recap.MyMap": {
                "type": "object",
                "additionalProperties": {"$ref": "#/$defs/build.recap.MapValue"},
            },
            "build.recap.MyEnum": {"type": "string", "enum": ["A", "B", "C"]},
            "build.recap.NestedInt": {"type": "integer"},
            "build.recap.NestedStruct": {
                "type": "object",
                "properties": {
                    "nested_int_field": {"$ref": "#/$defs/build.recap.NestedInt"},
                },
                "required": ["nested_int_field"],
            },
        },
        "type": "object",
        "properties": {
            "int_field": {"$ref": "#/$defs/build.recap.MyInt"},
            "string_field": {"$ref": "#/$defs/build.recap.MyString"},
            "bytes_field": {"$ref": "#/$defs/build.recap.MyBytes"},
            "float_field": {"$ref": "#/$defs/build.recap.MyFloat"},
            "bool_field": {"$ref": "#/$defs/build.recap.MyBool"},
            "null_field": {"$ref": "#/$defs/build.recap.MyNull"},
            "list_field": {"$ref": "#/$defs/build.recap.MyList"},
            "map_field": {"$ref": "#/$defs/build.recap.MyMap"},
            "enum_field": {"$ref": "#/$defs/build.recap.MyEnum"},
            "nested_struct_field": {"$ref": "#/$defs/build.recap.NestedStruct"},
        },
        "required": [
            "int_field",
            "string_field",
            "bytes_field",
            "float_field",
            "bool_field",
            "null_field",
            "list_field",
            "map_field",
            "enum_field",
            "nested_struct_field",
        ],
    }

    Draft202012Validator.check_schema(expected_schema)
    assert schema == expected_schema


def test_from_recap_types_alias_with_optional_field():
    struct = ListType(
        values=StructType(
            fields=[
                UnionType(
                    alias="build.recap.enabledToggle",
                    types=[NullType(), BoolType()],
                    name="enabled",
                    default=None,
                ),
            ],
        ),
    )

    schema = JSONSchemaConverter().from_recap(struct)

    expected_schema = {
        "type": "array",
        "items": {
            "type": "object",
            "properties": {
                "enabled": {
                    "$ref": "#/$defs/build.recap.enabledToggle",
                }
            },
        },
        "$defs": {
            "build.recap.enabledToggle": {
                "type": "boolean",
                "default": None,
            }
        },
    }

    Draft202012Validator.check_schema(expected_schema)
    assert schema == expected_schema


def test_from_recap_types_alias_with_optional_non_null():
    struct = ListType(
        values=StructType(
            fields=[
                UnionType(
                    alias="build.recap.enabledToggle",
                    types=[NullType(), BoolType()],
                    name="enabled",
                    default=True,
                ),
            ],
        ),
    )

    schema = JSONSchemaConverter().from_recap(struct)

    expected_schema = {
        "type": "array",
        "items": {
            "type": "object",
            "properties": {
                "enabled": {
                    "$ref": "#/$defs/build.recap.enabledToggle",
                }
            },
        },
        "$defs": {
            "build.recap.enabledToggle": {
                "type": "boolean",
                "default": True,
            }
        },
    }

    Draft202012Validator.check_schema(expected_schema)
    assert schema == expected_schema


def test_from_recap_types_union_type():
    struct = StructType(
        fields=[
            UnionType(
                alias="build.recap.UnionExample",
                types=[IntType(bits=32), StringType()],
                name="example_field",
            ),
        ],
    )

    schema = JSONSchemaConverter().from_recap(struct)

    expected_schema = {
        "type": "object",
        "properties": {
            "example_field": {
                "$ref": "#/$defs/build.recap.UnionExample",
            },
        },
        "$defs": {
            "build.recap.UnionExample": {
                "oneOf": [
                    {
                        "type": "integer",
                    },
                    {
                        "type": "string",
                    },
                ],
            },
        },
        "required": ["example_field"],
    }

    Draft202012Validator.check_schema(expected_schema)
    assert schema == expected_schema


def test_unsupported_json_schema_feature_to_unknown_type():
    json_schema = """
    {
        "type": "object",
        "properties": {
            "custom_feature": {"type": "magic"}
        }
    }
    """
    struct_type = JSONSchemaConverter().to_recap(json_schema)
    assert isinstance(struct_type, StructType)
    assert len(struct_type.fields) == 1
    unknown_type = struct_type.fields[0]
    assert isinstance(unknown_type, UnionType)  # Assuming all fields are treated as optional
    unknown_type = unknown_type.types[1]  # Skip the NullType in the union
    assert isinstance(unknown_type, UnknownType)
    assert unknown_type.description == "Unsupported JSON schema type encountered"


def test_unknown_type_with_description():
    json_schema = """
    {
        "type": "magic",
        "description": "This is a magical custom type"
    }
    """
    struct_type = JSONSchemaConverter().to_recap(json_schema)
    assert isinstance(struct_type, StructType), "Expected StructType"
    # Assuming StructType.fields is a list of dictionaries with 'name' and 'type' keys
    unknown_field = next((field for field in struct_type.fields if field['name'] == "unknown_field"), None)
    assert unknown_field is not None, "StructType does not contain an 'unknown_field'"
    assert isinstance(unknown_field['type'], UnknownType), "Expected 'unknown_field' to be UnknownType"
    assert unknown_field['type'].description == "This is a magical custom type", "UnknownType description does not match"


def test_nested_unknown_type_within_struct():
    json_schema = """
    {
        "type": "object",
        "properties": {
            "nested_unknown": {
                "type": "object",
                "properties": {
                    "magic_property": {"type": "magic"}
                }
            }
        }
    }
    """
    struct_type = JSONSchemaConverter().to_recap(json_schema)
    assert isinstance(struct_type, StructType)
    nested_struct = struct_type.fields[0]
    assert isinstance(nested_struct, UnionType)  # Assuming optional
    nested_struct = nested_struct.types[1]
    assert isinstance(nested_struct, StructType)
    unknown_type = nested_struct.fields[0]
    assert isinstance(unknown_type, UnionType)
    unknown_type = unknown_type.types[1]
    assert isinstance(unknown_type, UnknownType)


def test_union_type_including_unknown_type():
    json_schema = """
    {
        "type": "object",
        "properties": {
            "union_with_unknown": {
                "type": ["string", "magic"]
            }
        }
    }
    """
    struct_type = JSONSchemaConverter().to_recap(json_schema)
    assert isinstance(struct_type, StructType), "Expected StructType"
    union_field = struct_type.fields[0]
    assert isinstance(union_field, UnionType), "Expected UnionType"
    assert any(isinstance(t, NullType) for t in union_field.types), "Expected NullType in Union"
    assert any(isinstance(t, UnknownType) for t in union_field.types), "Expected UnknownType in Union"


def test_proxy_type_resolving_to_unknown_type():
    converter = JSONSchemaConverter()
    registry = converter.registry
    alias = "com.example.unknown"
    unknown_type = UnknownType(description="A mysterious type.", alias=alias)
    registry.register_alias(unknown_type)
    proxy_type = ProxyType(alias=alias, registry=registry)
    resolved_type = proxy_type.resolve()
    assert isinstance(resolved_type, UnknownType), "The resolved type should be UnknownType"
    assert resolved_type.description == unknown_type.description, "The description of the resolved UnknownType does not match"
