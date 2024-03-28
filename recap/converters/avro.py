import json
from typing import Any

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
    RecapType,
    RecapTypeRegistry,
    StringType,
    StructType,
    UnionType,
    UnknownType,
)


class AvroConverter:
    def __init__(self) -> None:
        self.registry = RecapTypeRegistry()

    def from_recap(self, recap_type: RecapType) -> dict[str, Any]:
        """
        Convert a Recap type to an Avro schema.

        :param recap_type: The Recap type to convert.
        :return: The Avro schema.
        """

        avro_schema = self._from_recap(recap_type)
        if isinstance(avro_schema, str):
            avro_schema = {"type": avro_schema}
        return avro_schema

    def _from_recap(
        self,
        recap_type: RecapType,
    ) -> dict[str, Any] | str:
        """
        Convert a Recap type to an Avro schema. Can return a string if the
        schema is simple.

        :param recap_type: The Recap type to convert.
        :return: The Avro schema or simple string type.
        """

        avro_schema = {}

        if recap_type.doc:
            avro_schema["doc"] = recap_type.doc

        if name := recap_type.extra_attrs.get("name"):
            avro_schema["name"] = name

        if "default" in recap_type.extra_attrs:
            avro_schema["default"] = recap_type.extra_attrs["default"]

        if (alias := recap_type.alias) and "." in alias:
            # If the alias is not naked (built-in), define it in Avro. Built-in
            # types are always resolved (so "int32" always becomes "int",
            # "decimal256" always becomes a bytes with logicalType "decimal",
            # etc.)
            avro_schema["aliases"] = [alias]

        match recap_type:
            case RecapType(logical=str()):
                avro_schema |= self._from_recap_logical(recap_type)
            case NullType():
                avro_schema["type"] = "null"
            case BoolType():
                avro_schema["type"] = "boolean"
            case IntType(bits=int(bits), signed=True) if bits <= 32:
                avro_schema["type"] = "int"
            case IntType(bits=int(bits), signed=bool(signed)) if (
                bits <= 32 and not signed
            ) or (bits <= 64 and signed):
                avro_schema["type"] = "long"
            case IntType(bits=int(bits), signed=bool(signed)):
                precision = len(str(2 ** (bits - (1 if signed else 0)))) - 1
                avro_schema |= {
                    "type": "bytes",
                    "logicalType": "decimal",
                    "precision": precision,
                }
            case FloatType(bits=int(bits)) if bits <= 32:
                avro_schema["type"] = "float"
            case FloatType(bits=int(bits)) if bits <= 64:
                avro_schema["type"] = "double"
            case StringType(bytes_=int(bytes_)) if bytes_ <= 9_223_372_036_854_775_807:
                avro_schema["type"] = "string"
            case BytesType(
                bytes_=int(bytes_),
                variable=True,
            ) if bytes_ <= 9_223_372_036_854_775_807:
                avro_schema["type"] = "bytes"
            case BytesType(
                bytes_=int(bytes_),
                variable=False,
            ) if bytes_ <= 9_223_372_036_854_775_807:
                avro_schema["type"] = "fixed"
                avro_schema["size"] = bytes_
            case StructType(fields=list(struct_fields)):
                avro_schema["type"] = "record"
                record_fields = []
                for struct_field in struct_fields:
                    record_field = {}
                    field_type = self._from_recap(struct_field)
                    if isinstance(field_type, dict):
                        record_field |= field_type
                    elif isinstance(field_type, str):
                        record_field["type"] = field_type
                    else:
                        raise ValueError(f"Unexpected field type: {field_type}")
                    record_fields.append(record_field)
                avro_schema["fields"] = record_fields
            case EnumType(symbols=list(symbols)):
                avro_schema["type"] = "enum"
                avro_schema["symbols"] = symbols
            case ListType(values=values):
                avro_schema["type"] = "array"
                avro_schema["items"] = self._from_recap(values)
            case MapType(
                keys=StringType(),
                values=values,
            ):  # Avro only supports string keys
                avro_schema["type"] = "map"
                avro_schema["values"] = self._from_recap(values)
            case UnionType(types=list(types)):
                avro_schema["type"] = [self._from_recap(t) for t in types]
            case ProxyType(alias=str(alias)):
                if "." not in alias:
                    # Builtin types should be resolved
                    alias_type = self._from_recap(recap_type.resolve())
                    if isinstance(alias_type, dict):
                        avro_schema |= alias_type
                    else:
                        avro_schema["type"] = alias
                else:
                    # Fully qualified (non-builtin) aliases should just be referenced.
                    avro_schema["type"] = alias
                # Never redefine an alias. Needed because we set alias at the top of
                # the func, but the ProxyType alias param has a different semantic
                # meaning from other types.
                avro_schema.pop("aliases", None)
            case _:
                avro_schema["type"] = "unknown"

        if len(avro_schema) == 1 and isinstance(avro_schema["type"], str):
            # Convert {"type": "type"} to "type"
            avro_schema = avro_schema["type"]

        return avro_schema

    def _from_recap_logical(self, recap_type: RecapType) -> dict[str, Any]:
        match recap_type:
            case BytesType(
                bytes_=int(bytes_),
                variable=bool(),
                logical=str(logical),
            ) if (
                bytes_ <= 9_223_372_036_854_775_807
                and logical == "build.recap.Decimal"
                and isinstance(recap_type.extra_attrs.get("precision"), int)
            ):
                return {
                    "type": "bytes",
                    "logicalType": "decimal",
                    "precision": recap_type.extra_attrs["precision"],
                    "scale": recap_type.extra_attrs.get("scale", 0),
                }
            case IntType(bits=int(bits), signed=True, logical=str(logical)) if (
                bits <= 32 and logical == "build.recap.Date"
            ):
                return {
                    "type": "int",
                    "logicalType": "date",
                }
            case IntType(bits=int(bits), signed=True, logical=str(logical)) if (
                bits <= 32
                and logical == "build.recap.Time"
                and recap_type.extra_attrs.get("unit") == "millisecond"
            ):
                return {
                    "type": "int",
                    "logicalType": "time-millis",
                }
            case IntType(bits=int(bits), signed=True, logical=str(logical)) if (
                bits <= 64
                and logical == "build.recap.Time"
                and recap_type.extra_attrs.get("unit") == "microsecond"
            ):
                return {
                    "type": "long",
                    "logicalType": "time-micros",
                }
            case IntType(bits=int(bits), signed=True, logical=str(logical)) if (
                bits <= 64
                and logical == "build.recap.Timestamp"
                and recap_type.extra_attrs.get("unit") == "millisecond"
            ):
                return {
                    "type": "long",
                    "logicalType": "timestamp-millis",
                }
            case IntType(bits=int(bits), signed=True, logical=str(logical)) if (
                bits <= 64
                and logical == "build.recap.Timestamp"
                and recap_type.extra_attrs.get("unit") == "microsecond"
            ):
                return {
                    "type": "long",
                    "logicalType": "timestamp-micros",
                }
            case BytesType(
                bytes_=12,
                variable=False,
                logical=str(logical),
            ) if (
                logical == "build.recap.Interval"
                and recap_type.extra_attrs.get("unit") == "millisecond"
            ):
                return {
                    "type": "fixed",
                    "logicalType": "duration",
                    "size": 12,
                }
            case StringType(bytes_=int(bytes_), logical=str(logical)) if (
                bytes_ <= 9_223_372_036_854_775_807 and logical == "build.recap.UUID"
            ):
                return {
                    "type": "string",
                    "logicalType": "uuid",
                }
            case _:
                raise ValueError(f"Unsupported Recap logical type: {recap_type}")

    def to_recap(
        self,
        avro_schema_str: str,
        namespace: str | None = None,
    ) -> StructType:
        avro_schema = json.loads(avro_schema_str)
        recap_schema = self._parse(avro_schema, namespace)
        if not isinstance(recap_schema, StructType):
            raise ValueError("Avro schema must be a record")
        return recap_schema

    def _parse(
        self,
        avro_schema: dict | str,
        namespace: str | None,
    ) -> RecapType:
        return_type = None
        alias: str | None = None
        extra_attrs = {}

        if isinstance(avro_schema, str):
            avro_schema = {"type": avro_schema}
        if "doc" in avro_schema:
            extra_attrs["doc"] = avro_schema["doc"]
        if "namespace" in avro_schema:
            namespace = avro_schema["namespace"]
        if "name" in avro_schema:
            name = avro_schema["name"]
            if "." in avro_schema["name"]:
                namespace, name = avro_schema["name"].rsplit(".", 1)
            if not namespace:
                namespace = "_root"
            extra_attrs["name"] = name
            alias = f"{namespace}.{name}"
        if "default" in avro_schema:
            extra_attrs["default"] = avro_schema["default"]
        if logical_type := avro_schema.get("logicalType"):
            return self._parse_logical(logical_type, avro_schema, extra_attrs)

        match avro_schema:
            case {"type": "null"}:
                return_type = NullType(alias=alias, **extra_attrs)
            case {"type": "boolean"}:
                return_type = BoolType(alias=alias, **extra_attrs)
            case {"type": "int"}:
                return_type = IntType(32, signed=True, alias=alias, **extra_attrs)
            case {"type": "long"}:
                return_type = IntType(64, signed=True, alias=alias, **extra_attrs)
            case {"type": "float"}:
                return_type = FloatType(32, alias=alias, **extra_attrs)
            case {"type": "double"}:
                return_type = FloatType(64, alias=alias, **extra_attrs)
            case {"type": "bytes"}:
                return_type = BytesType(
                    9_223_372_036_854_775_807,
                    alias=alias,
                    **extra_attrs,
                )
            case {
                "type": "fixed",
                "size": int(size),
            } if size <= 9_223_372_036_854_775_807:
                return_type = BytesType(
                    size,
                    alias=alias,
                    **extra_attrs,
                )
            case {"type": "string"}:
                return_type = StringType(
                    9_223_372_036_854_775_807,
                    alias=alias,
                    **extra_attrs,
                )
            case {"type": "record", "fields": fields}:
                fields = [
                    self._parse(field, namespace)
                    for field in avro_schema.get("fields", [])
                ]
                return_type = StructType(fields, alias=alias, **extra_attrs)
            case {"type": "enum", "symbols": symbols}:
                return_type = EnumType(symbols, alias=alias, **extra_attrs)
            case {"type": "array", "items": items}:
                values = self._parse(items, namespace)
                return_type = ListType(values, alias=alias, **extra_attrs)
            case {"type": "map", "values": values}:
                keys = StringType(9_223_372_036_854_775_807)
                return_type = MapType(
                    keys,
                    self._parse(values, namespace),
                    alias=alias,
                    **extra_attrs,
                )
            case {"type": "union", "types": types} | {"type": list(types)}:
                return_type = UnionType(
                    [self._parse(t, namespace) for t in types],
                    alias=alias,
                    **extra_attrs,
                )
            case {"type": str(type_alias)}:
                if "." not in type_alias:
                    type_alias = f"{namespace}.{type_alias}"

                # Short circuit so we don't re-register aliases for proxies
                return ProxyType(type_alias, self.registry, **extra_attrs)
            case {"type": dict(type_)}:
                return_type = self._parse(type_, namespace)

                # Don't pass extra_attrs into _parse since we don't want field
                # "name" to overwrite "alias" for record/enum/fixed.
                return_type.extra_attrs |= extra_attrs

                # Short circuit so we don't re-register aliases for nested types
                return return_type
            case _:
                return UnknownType(**extra_attrs)

        if return_type.alias is not None:
            self.registry.register_alias(return_type)

        return return_type

    def _parse_logical(
        self,
        logical_type: str,
        avro_schema: dict,
        extra_attrs: dict,
    ) -> RecapType:
        match logical_type:
            case "decimal":
                return BytesType(
                    logical="build.recap.Decimal",
                    bytes_=avro_schema.get("size", 9_223_372_036_854_775_807),
                    variable=avro_schema["type"] == "fixed",
                    precision=avro_schema["precision"],
                    scale=avro_schema.get("scale", 0),
                    **extra_attrs,
                )
            case "uuid":
                return StringType(
                    logical="build.recap.UUID",
                    bytes_=36,
                    variable=False,
                    **extra_attrs,
                )
            case "date":
                return IntType(
                    logical="build.recap.Date",
                    bits=32,
                    signed=True,
                    unit="day",
                    **extra_attrs,
                )
            case "time-millis":
                return IntType(
                    logical="build.recap.Time",
                    bits=32,
                    signed=True,
                    unit="millisecond",
                    **extra_attrs,
                )
            case "time-micros":
                return IntType(
                    logical="build.recap.Time",
                    bits=64,
                    signed=True,
                    unit="microsecond",
                    **extra_attrs,
                )
            case "timestamp-millis":
                return IntType(
                    logical="build.recap.Timestamp",
                    bits=64,
                    signed=True,
                    unit="millisecond",
                    **extra_attrs,
                )
            case "timestamp-micros":
                return IntType(
                    logical="build.recap.Timestamp",
                    bits=64,
                    signed=True,
                    unit="microsecond",
                    **extra_attrs,
                )
            case "duration":
                return BytesType(
                    logical="build.recap.Interval",
                    bytes_=12,
                    signed=True,
                    unit="millisecond",
                    **extra_attrs,
                )
            case _:
                return UnknownType(**extra_attrs)
