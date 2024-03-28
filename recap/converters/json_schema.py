from __future__ import annotations

import json
import re
from typing import Any, Callable
from urllib.parse import urlparse

import httpx
from referencing import Registry, Resource, jsonschema, retrieval

from recap.types import (
    BUILTIN_ALIASES,
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

AliasStrategy = Callable[[str], str]


class JSONSchemaConverter:
    def __init__(self, json_registry: Registry | None = None):
        self.registry = RecapTypeRegistry()
        self.json_registry = json_registry or Registry(
            retrieve=JSONSchemaConverter.httpx_retrieve
        )

    def to_recap(
        self,
        json_schema_str: str,
        alias_strategy: AliasStrategy | None = None,
    ) -> StructType:
        alias_strategy = alias_strategy or JSONSchemaConverter.urn_to_alias
        json_schema = json.loads(json_schema_str)
        recap_schema = self._parse(json_schema, alias_strategy)
        if isinstance(recap_schema, UnknownType):
            return StructType(fields=[{"name": "unknown_field", "type": recap_schema}],
                              description=recap_schema.description)
        if not isinstance(recap_schema, StructType):
            raise ValueError("JSON schema must be an object")
        return recap_schema

    def _parse(
        self,
        json_schema: dict | str,
        alias_strategy: AliasStrategy,
    ) -> RecapType:
        extra_attrs = {}
        # Check if json_schema is just a string representing a basic type, and
        # convert to a dict with a "type" property if so
        if isinstance(json_schema, str):
            json_schema = {"type": json_schema}
        if "description" in json_schema:
            extra_attrs["doc"] = json_schema["description"]
        if "default" in json_schema:
            extra_attrs["default"] = json_schema["default"]
        if "$id" in json_schema:
            resource = Resource.from_contents(json_schema, jsonschema.DRAFT202012)
            resource_id = resource.id()
            assert resource_id is not None, f"$id must be set for {json_schema}"
            self.json_registry = resource @ self.json_registry
            extra_attrs["alias"] = alias_strategy(resource_id)

        match json_schema:
            # Special handling for "type" defined as a list of strings like
            # {"type": ["string", "boolean"]}
            case {"type": list(type_list)}:
                types = [self._parse(s, alias_strategy) for s in type_list]
                return UnionType(types, **extra_attrs)
            case {"type": "object", "properties": properties}:
                fields = []
                for name, prop in properties.items():
                    field = self._parse(prop, alias_strategy)
                    # If not explicitly required, make optional by ensuring the
                    # field is nullable, and has a default
                    if name not in json_schema.get("required", []):
                        if not field.is_nullable():
                            field = field.make_nullable()
                        # is_nullable doesn't guarantee a default of none, so
                        # set it here.
                        if "default" not in field.extra_attrs:
                            field.extra_attrs["default"] = None

                    field.extra_attrs["name"] = name
                    fields.append(field)
                return StructType(fields, **extra_attrs)
            case {"type": "array", "items": items}:
                values = self._parse(items, alias_strategy)
                return ListType(values, **extra_attrs)
            case {"type": "string", "format": "bytes"}:
                return BytesType(**extra_attrs)
            case {"type": "string", "format": "date"}:
                return StringType(logical="org.iso.8601.Date", **extra_attrs)
            case {"type": "string", "format": "date-time"}:
                return StringType(logical="org.iso.8601.DateTime", **extra_attrs)
            case {"type": "string", "format": "time"}:
                return StringType(logical="org.iso.8601.Time", **extra_attrs)
            case {"type": "string"}:
                return StringType(**extra_attrs)
            case {"type": "number"}:
                return FloatType(bits=64, **extra_attrs)
            case {"type": "integer"}:
                return IntType(bits=32, signed=True, **extra_attrs)
            case {"type": "boolean"}:
                return BoolType(**extra_attrs)
            case {"type": "null"}:
                return NullType(**extra_attrs)
            case {"$ref": str(urn)} | {"$dynamicRef": str(urn)}:
                try:
                    # If no KeyError is thrown here, we've already crawled this,
                    # so we can just return a ProxyType referencing the original.
                    resource = self.json_registry[urn]
                    assert (
                        resource.id() is not None
                    ), f"$id must be set for {resource.contents}"
                    alias = alias_strategy(str(resource.id()))
                    return ProxyType(alias, self.registry, **extra_attrs)
                except KeyError:
                    # We haven't crawled this type yet, so crawl and define the
                    # type as a normal Recap type with an alias set.
                    retrieved = self.json_registry.get_or_retrieve(urn)
                    resource = retrieved.value
                    self.json_registry = (
                        retrieved.registry @ self.json_registry
                    )  # pyright: ignore[reportGeneralTypeIssues]
                    return self._parse(resource.contents, alias_strategy)
            case _:
                description = json_schema.get("description", "Unsupported JSON schema type encountered")
                return UnknownType(description=description, **extra_attrs)

    def from_recap(self, recap_type: RecapType) -> dict[str, Any]:
        """
        Convert a Recap type to a JSON schema. This method is recursive, so
        any nested types will be converted as well. The returned JSON schema
        will have a "$defs" key containing any aliased types.

        :param recap_type: The Recap type to convert.
        :return: A JSON schema.
        """

        type_dict = self._convert_field(recap_type)

        if defs := self._generate_alias_defs(recap_type):
            type_dict["$defs"] = defs

        return type_dict

    def _generate_alias_defs(self, recap_type: RecapType) -> dict[str, Any]:
        """
        Generate a dictionary of alias definitions for the given Recap type.
        Recursively generates definitions for any nested types, as well.
        This method is used to generate the "$defs" key in the top-level.

        :param recap_type: The Recap type to generate definitions for.
        :return: A dictionary of alias definitions.
        """

        defs = {}

        if (alias := recap_type.alias) and alias not in BUILTIN_ALIASES:
            # Don't use $ref for concrete types, since we're defining them,
            # not referencing them.
            defs[alias] = self._convert_field(recap_type, False)

        if isinstance(recap_type, StructType):
            for field in recap_type.fields:
                defs |= self._generate_alias_defs(field)
        elif isinstance(recap_type, ListType):
            defs |= self._generate_alias_defs(recap_type.values)
        elif isinstance(recap_type, UnionType):
            for value in recap_type.types:
                defs |= self._generate_alias_defs(value)
        elif isinstance(recap_type, MapType):
            defs |= self._generate_alias_defs(recap_type.values)

        return defs

    def _convert_field(
        self,
        field: RecapType,
        use_refs: bool = True,
    ) -> dict[str, Any]:
        """
        Convert a Recap type to a JSON schema type.

        :param field: The Recap type to convert.
        :param use_refs: If true, use $ref for concrete types with aliases.
        :return: A JSON schema type.
        """

        type_dict = {}

        if "default" in field.extra_attrs:
            type_dict |= {"default": field.extra_attrs["default"]}
        if doc := field.doc:
            type_dict |= {"description": doc}

        match field:
            case RecapType(alias=str(alias)) if use_refs and not isinstance(
                field,
                ProxyType,
            ):
                # This is a concrete type with an alias. Return the reference
                # since _generate_alias_defs will handle defining the type.
                type_dict = {"$ref": f"#/$defs/{alias}"}
            case UnionType(types=types):
                # If field is optional, just return the nested type.
                # from_recap will mark the field as required in the struct.
                if field.is_optional:
                    non_null_types = [t for t in types if not isinstance(t, NullType)]
                    assert len(non_null_types) == 1
                    type_dict |= self._convert_field(non_null_types[0])
                else:
                    type_dict |= {"oneOf": [self._convert_field(t) for t in types]}
            case StructType():
                type_dict |= {"type": "object", "properties": {}}
                for field in field.fields:
                    if field_name := field.extra_attrs.get("name"):
                        type_dict["properties"][field_name] = self._convert_field(field)

                        if not isinstance(field, UnionType) or not field.is_optional:
                            type_dict.setdefault("required", []).append(field_name)
                    else:
                        raise ValueError(f"Field {field} has no name")
            case ListType(values=values):
                type_dict |= {
                    "type": "array",
                    "items": self._convert_field(values),
                }
            case MapType(values=values):
                type_dict |= {
                    "type": "object",
                    "additionalProperties": self._convert_field(values),
                }
            case EnumType(symbols=symbols):
                type_dict |= {"type": "string", "enum": symbols}
            case BoolType():
                type_dict |= {"type": "boolean"}
            case IntType():
                type_dict |= {"type": "integer"}
            case FloatType():
                type_dict |= {"type": "number"}
            case StringType():
                type_dict |= {"type": "string"}
            case BytesType():
                type_dict |= {"type": "string", "format": "byte"}
            case NullType():
                type_dict |= {"type": "null"}
            case ProxyType(alias=alias) if alias in BUILTIN_ALIASES or len(
                field.extra_attrs
            ) > 0:
                # If there are attribute overrides, we can't use refs. JSON
                # schema doesn't support $def overrides. Also, if the alias
                # is a built-in type, convert to standard types instead of $defs
                return self._convert_field(field.resolve())
            case ProxyType(alias=str(alias)):
                return type_dict | {"$ref": f"#/$defs/{alias}"}
            case UnknownType():
                type_dict |= {"type": "unknown", "description": field.description}
        return type_dict

    @staticmethod
    def urn_to_alias(urn: str) -> str:
        """
        Convert a URN to a dotted alias name. The following rules are used:

        - The domain is reversed, e.g. "example.com" becomes "com.example"
        - The path is converted to lowercase and special characters are replaced
          with dots, e.g. "/foo/bar" becomes "foo.bar"
        - The domain and path are combined, e.g. "com.example/foo.bar"

        It's possible that this function will generate the same alias for
        different URNs. If this happens, you can provide a custom alias
        strategy to the `to_recap` method.

        :param urn: The URN to convert
        :return: The dotted alias
        """

        # Parse the URN/URL
        parsed = urlparse(urn)

        # Reverse domain
        domain_parts = parsed.netloc.split(".")
        domain_parts.reverse()
        domain = ".".join(domain_parts)

        # Replace special characters in the path, convert to lowercase
        path = parsed.path + parsed.fragment
        path = re.sub(r"[^a-zA-Z0-9]", ".", path)
        path = path.lower()

        # Combine domain and path
        dotted_type = domain
        if path and path != ".":
            dotted_type += "." + path.strip(".")

        return dotted_type

    @staticmethod
    @retrieval.to_cached_resource()
    def httpx_retrieve(uri: str):
        return httpx.get(uri).text
