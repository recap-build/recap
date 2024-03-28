from __future__ import annotations

import copy
import inspect
from re import fullmatch
from typing import Any

ALIAS_REGEX = r"^[a-zA-Z_][a-zA-Z0-9_]*(?:\.[a-zA-Z_][a-zA-Z0-9_]*)+$"


class RecapType:
    """Base class for all Recap types."""

    def __init__(
        self,
        type_: str,
        logical: str | None = None,
        alias: str | None = None,
        doc: str | None = None,
        **extra_attrs,
    ):
        self.type_ = type_
        self.logical = logical
        self.alias = alias
        self.doc = doc
        self.extra_attrs = extra_attrs

    def make_nullable(self) -> UnionType:
        """
        Make a type nullable by wrapping it in a union with null. Promote the
        doc and default values to the union.

        The nested type is a copy of `self` with `doc` and `default` removed.

        :return: A union type with null and the original type. Doc and default
            are promoted to the union if they're set.
        """

        RecapTypeClass = self.__class__
        attrs = vars(self)
        # Filter private attributes
        attrs = {k: v for k, v in attrs.items() if not k.startswith("_")}
        attrs.pop("type_", None)
        # Move doc to the union type
        doc = attrs.pop("doc", None)
        # Unnest extra_attrs for copy or we end up with extra_attrs["extra_attrs"]
        extra_attrs = attrs.pop("extra_attrs", {})
        union_attrs = {
            "default": extra_attrs.pop("default", None),
            "doc": doc,
        }
        # Move field name to the union type
        if "name" in extra_attrs:
            union_attrs["name"] = extra_attrs.pop("name")
        # Create a copy of the type with doc, default, and name removed
        type_copy = RecapTypeClass(**attrs, **extra_attrs)
        if RecapTypeClass == UnionType:
            # Avoid UnionType(types=[NullType(), UnionType(...)])
            # Instead, just add NullType and default=None to the existing union
            type_copy = UnionType(**attrs, **extra_attrs, **union_attrs)
        else:
            type_copy = UnionType([type_copy], **union_attrs)
        # If a NullType isn't in the UnionType, add it. Can't do `NullType() in
        # type_copy.types` because equality checks extra_attrs, which can vary.
        # Instead, just look for any NullType instance.
        if not list(filter(lambda t: isinstance(t, NullType), type_copy.types)):
            type_copy.types.insert(0, NullType())
        return type_copy

    def is_nullable(self) -> bool:
        """
        Returns True if the type is nullable.
        :return: True if the type is nullable.
        """

        if isinstance(self, UnionType):
            # Can't do `NullType() in type_copy.types` because equality checks
            # extra_attrs, which can vary. Instead, just look for any NullType
            # instance.
            for t in self.types:
                if isinstance(t, NullType):
                    return True

            return False

        return isinstance(self, NullType)

    def validate(self) -> None:
        # Default to valid type
        pass

    def __eq__(self, other):
        if type(self) is type(other):
            return (
                self.type_,
                self.logical,
                self.alias,
                self.doc,
                self.extra_attrs,
            ) == (other.type_, other.logical, other.alias, other.doc, other.extra_attrs)
        return False

    def __repr__(self):
        attrs = vars(self)
        attrs_str = ", ".join(f"{k}={v}" for k, v in attrs.items())
        return f"{self.__class__.__name__}({attrs_str})"


class NullType(RecapType):
    """Represents a null Recap type."""

    def __init__(self, **extra_attrs):
        super().__init__("null", **extra_attrs)


class BoolType(RecapType):
    """Represents a boolean Recap type."""

    def __init__(self, **extra_attrs):
        super().__init__("bool", **extra_attrs)


class IntType(RecapType):
    """Represents an integer Recap type."""

    def __init__(self, bits: int, signed: bool = True, **extra_attrs):
        super().__init__("int", **extra_attrs)
        self.bits = bits
        self.signed = signed

    def __eq__(self, other):
        return super().__eq__(other) and (self.bits, self.signed) == (
            other.bits,
            other.signed,
        )

    def validate(self) -> None:
        if self.bits < 1 or self.bits > 2_147_483_647:
            raise ValueError("Bits must be between 1 and 2,147,483,647")


class FloatType(RecapType):
    """Represents a floating point Recap type."""

    def __init__(self, bits: int, **extra_attrs):
        super().__init__("float", **extra_attrs)
        self.bits = bits

    def __eq__(self, other):
        return super().__eq__(other) and self.bits == other.bits

    def validate(self) -> None:
        if self.bits < 1 or self.bits > 2_147_483_647:
            raise ValueError("Bits must be between 1 and 2,147,483,647")


class StringType(RecapType):
    """Represents a string Recap type."""

    def __init__(self, bytes_: int | None = None, variable: bool = True, **extra_attrs):
        super().__init__("string", **extra_attrs)
        self.bytes_ = bytes_
        self.variable = variable

    def __eq__(self, other):
        return super().__eq__(other) and (self.bytes_, self.variable) == (
            other.bytes_,
            other.variable,
        )

    def validate(self) -> None:
        if not self.variable and self.bytes_ is None:
            raise ValueError("Fixed length bytes must have a length set")
        if self.bytes_ is not None and (
            self.bytes_ < 1 or self.bytes_ > 9_223_372_036_854_775_807
        ):
            raise ValueError("Bytes must be between 1 and 9,223,372,036,854,775,807")


class BytesType(RecapType):
    """Represents a bytes Recap type."""

    def __init__(self, bytes_: int | None = None, variable: bool = True, **extra_attrs):
        super().__init__("bytes", **extra_attrs)
        self.bytes_ = bytes_
        self.variable = variable

    def __eq__(self, other):
        return super().__eq__(other) and (self.bytes_, self.variable) == (
            other.bytes_,
            other.variable,
        )

    def validate(self) -> None:
        if not self.variable and self.bytes_ is None:
            raise ValueError("Fixed length bytes must have a length set")
        if self.bytes_ is not None and (
            self.bytes_ < 1 or self.bytes_ > 9_223_372_036_854_775_807
        ):
            raise ValueError("Bytes must be between 1 and 9,223,372,036,854,775,807")


class ListType(RecapType):
    """Represents a list Recap type."""

    def __init__(
        self,
        values: RecapType,
        length: int | None = None,
        variable: bool = True,
        **extra_attrs,
    ):
        super().__init__("list", **extra_attrs)
        self.values = values
        self.length = length
        self.variable = variable

    def __eq__(self, other):
        return super().__eq__(other) and (self.values, self.length, self.variable) == (
            other.values,
            other.length,
            other.variable,
        )

    def validate(self) -> None:
        if not self.variable and self.length is None:
            raise ValueError("Fixed length lists must have a length set")
        if self.length is not None and (
            self.length < 1 or self.length > 9_223_372_036_854_775_807
        ):
            raise ValueError(
                "List length must be between 0 and 9,223,372,036,854,775,807"
            )
        self.values.validate()


class MapType(RecapType):
    """Represents a map Recap type."""

    def __init__(self, keys: RecapType, values: RecapType, **extra_attrs):
        super().__init__("map", **extra_attrs)
        self.keys = keys
        self.values = values

    def __eq__(self, other):
        return super().__eq__(other) and (self.keys, self.values) == (
            other.keys,
            other.values,
        )

    def validate(self) -> None:
        self.keys.validate()
        self.values.validate()


class StructType(RecapType):
    """Represents a struct Recap type."""

    def __init__(self, fields: list[RecapType] | None = None, **extra_attrs):
        super().__init__("struct", **extra_attrs)
        self.fields = fields if fields is not None else []

    def __eq__(self, other):
        return super().__eq__(other) and self.fields == other.fields

    def validate(self) -> None:
        for field in self.fields:
            field.validate()


class EnumType(RecapType):
    """Represents an enum Recap type."""

    def __init__(self, symbols: list[str], **extra_attrs):
        super().__init__("enum", **extra_attrs)
        self.symbols = symbols

    def __eq__(self, other):
        return super().__eq__(other) and self.symbols == other.symbols


class UnionType(RecapType):
    """Represents a union Recap type."""

    def __init__(self, types: list[RecapType], **extra_attrs):
        super().__init__("union", **extra_attrs)
        self.types = types

    def __eq__(self, other):
        return super().__eq__(other) and self.types == other.types

    @property
    def is_optional(self) -> bool:
        """
        Returns True if the union is an optional type, that has...

        - a null type
        - a default value
        - a single non-null type

        :return: True if the union is an optional type
        """
        has_null = NullType() in self.types
        has_default = "default" in self.extra_attrs
        has_non_null = len(list(filter(lambda t: t != NullType(), self.types))) == 1
        return has_null and has_default and has_non_null


class ProxyType(RecapType):
    """Represents a proxy to an aliased Recap type."""

    def __init__(self, alias: str, registry: RecapTypeRegistry, **extra_attrs):
        super().__init__("proxy", **extra_attrs)
        self.alias = alias
        self.registry = registry
        self._resolved = None

    def resolve(self) -> RecapType:
        if self._resolved is None:
            self._resolved = copy.deepcopy(self.registry.from_alias(self.alias))
            # Apply attribute overrides
            for attr, value in self.extra_attrs.items():
                if hasattr(self._resolved, attr):
                    setattr(self._resolved, attr, value)
                else:
                    self._resolved.extra_attrs[attr] = value
        return self._resolved

    def __eq__(self, other):
        return super().__eq__(other) and self.alias == other.alias


class RecapTypeRegistry:
    """Class that handles Recap type registration and resolution."""

    def __init__(self):
        # Define and register built-in aliases
        self._type_registry: dict[str, RecapType] = copy.deepcopy(BUILTIN_ALIASES)

    def register_alias(self, recap_type: RecapType):
        alias = recap_type.alias
        if alias is None:
            raise ValueError("RecapType must have an alias.")
        if alias in self._type_registry:
            raise ValueError(f"Alias {recap_type.alias} is already used.")
        if fullmatch(ALIAS_REGEX, alias) is None:
            raise ValueError(f"Alias {alias} must be a fully qualified name.")
        recap_type = copy.deepcopy(recap_type)
        # Registry contains types without aliases so aliased types don't get
        # accidentally redefined when referenced.
        recap_type.alias = None
        # Do not include doc in aliases
        recap_type.doc = None
        # Do not include default in aliases
        recap_type.extra_attrs.pop("default", None)
        self._type_registry[alias] = recap_type

    def from_alias(self, alias: str) -> RecapType:
        try:
            return self._type_registry[alias]
        except KeyError:
            raise TypeError(f"No RecapType with alias {alias} found.")


class UnknownType(RecapType):
    """Represents an unknown or unsupported Recap type."""

    def __init__(self, description: str = "Unknown or unsupported type", **extra_attrs):
        super().__init__("unknown", **extra_attrs)
        self.description = description

    def __eq__(self, other):
        return super().__eq__(other) and self.description == other.description

    def __repr__(self):
        return f"{self.__class__.__name__}(description={self.description})"



def from_dict(
    type_dict: dict | list | str,
    registry: RecapTypeRegistry | None = None,
) -> RecapType:
    """
    Create a RecapType from a dictionary, list, or string. Lists are treated as
    unions and strings are treated as aliases or simple types (e.g. "null",
    "bool", "string", or "bytes").

    :param type_dict: A dictionary, list, or string representing a Recap type.
    :param registry: A RecapTypeRegistry to use for resolving aliases.
    :return: A RecapType.
    """

    if isinstance(type_dict, list):
        type_dict = {"type": "union", "types": type_dict}
    elif isinstance(type_dict, str):
        type_dict = {"type": type_dict}

    # Create a copy to avoid modifying the input dictionary
    type_dict = type_dict.copy()

    assert (
        type_dict.get("type") is not None
    ), "Type dictionary must have a 'type' field."

    # Support optional=True syntactic sugar
    if type_dict.pop("optional", False):
        # Special handling for reserved words in struct fields
        name = type_dict.pop("name", None)
        default = type_dict.pop("default", None)
        if type_dict["type"] != "union":
            type_dict = {
                "type": "union",
                "types": ["null", type_dict],
            }
        if "null" not in type_dict["types"]:
            type_dict["types"] = ["null"] + type_dict["types"]
        if name is not None:
            type_dict["name"] = name
        type_dict["default"] = default

    registry = registry or RecapTypeRegistry()
    type_name = type_dict.pop("type")

    if isinstance(type_name, list):
        # If type is a list, handle as a union
        union_types = []
        for t in type_name:
            if isinstance(t, dict):
                union_types.append(from_dict(t, registry))
            elif isinstance(t, str):
                union_types.append(from_dict({"type": t}, registry))
        recap_type = UnionType(union_types, **type_dict)
    elif isinstance(type_name, str):
        match type_name:
            case "null":
                recap_type = NullType(**type_dict)
            case "bool":
                recap_type = BoolType(**type_dict)
            case "int":
                if "bits" not in type_dict:
                    raise ValueError("'bits' attribute is required for 'int' type.")
                recap_type = IntType(**type_dict)
            case "float":
                if "bits" not in type_dict:
                    raise ValueError("'bits' attribute is required for 'float' type.")
                recap_type = FloatType(**type_dict)
            case "string":
                if "bytes" in type_dict:
                    type_dict["bytes_"] = type_dict.pop("bytes")
                recap_type = StringType(**type_dict)
            case "bytes":
                if "bytes" in type_dict:
                    type_dict["bytes_"] = type_dict.pop("bytes")
                recap_type = BytesType(**type_dict)
            case "list":
                if "values" not in type_dict:
                    raise ValueError("'values' attribute is required for 'list' type.")
                recap_type = ListType(
                    from_dict(type_dict.pop("values"), registry),
                    **type_dict,
                )
            case "map":
                if "keys" not in type_dict or "values" not in type_dict:
                    raise ValueError(
                        "'keys' and 'values' attributes are required for 'map' type."
                    )
                recap_type = MapType(
                    from_dict(type_dict.pop("keys"), registry),
                    from_dict(type_dict.pop("values"), registry),
                    **type_dict,
                )
            case "struct":
                type_dict["fields"] = [
                    from_dict(f, registry) for f in type_dict.get("fields", [])
                ]
                recap_type = StructType(**type_dict)
            case "enum":
                if "symbols" not in type_dict:
                    raise ValueError("'symbols' attribute is required for 'enum' type.")
                recap_type = EnumType(**type_dict)
            case "union":
                if "types" not in type_dict:
                    raise ValueError("'types' attribute is required for 'union' type.")
                recap_type = UnionType(
                    [from_dict(t, registry) for t in type_dict.pop("types")],
                    **type_dict,
                )
            case "unknown":
                description = type_dict.pop("description", "Unknown or unsupported type")
                recap_type = UnknownType(description=description,  **type_dict)
            case _:
                recap_type = ProxyType(type_name, registry, **type_dict)
    else:
        raise ValueError("'type' must be a string or list.")

    recap_type.validate()

    # If alias exists, register the created RecapType
    if recap_type.alias is not None and not isinstance(recap_type, ProxyType):
        registry.register_alias(recap_type)

    return recap_type


def to_dict(recap_type: RecapType, clean=True, alias=True) -> dict | list | str:
    """
    Convert a RecapType to a dictionary, list, or string.

    :param recap_type: A RecapType.
    :param clean: If True, remove defaults, and make the dictionary as compact
        as possible.
    :param alias: If True, replace types that match an alias with the alias
        name.
    :return: A dictionary, list, or string representing a Recap type.  Lists
        are returned if clean=True and recap_type is a union with no extra
        attributes. Strings are returned if clean=True and recap_type is a
        simple type (e.g. "null", "bool", "string", or "bytes") or alias (e.g.
        "int32", "uint64", "decimal256", etc).
    """

    type_dict = {
        "type": recap_type.type_,
        "alias": recap_type.alias,
        "logical": recap_type.logical,
        "doc": recap_type.doc,
        **recap_type.extra_attrs,
    }

    match recap_type:
        case IntType(bits=bits, signed=sign):
            type_dict.update({"bits": bits, "signed": sign})
        case FloatType(bits=bits):
            type_dict["bits"] = bits
        case StringType(bytes_=bytes_, variable=variable):
            type_dict.update({"bytes": bytes_, "variable": variable})
        case BytesType(bytes_=bytes_, variable=variable):
            type_dict.update({"bytes": bytes_, "variable": variable})
        case ListType(values=values, length=length, variable=variable):
            type_dict.update(
                {
                    "values": to_dict(values, clean, alias),
                    "length": length,
                    "variable": variable,
                }
            )
        case MapType(keys=keys, values=values):
            type_dict.update(
                {
                    "keys": to_dict(keys, clean, alias),
                    "values": to_dict(values, clean, alias),
                }
            )
        case StructType(fields=fields):
            type_dict["fields"] = [
                to_dict(
                    field,
                    clean,
                    alias,
                )
                for field in fields
            ]
        case EnumType(symbols=symbols):
            type_dict["symbols"] = symbols
        case UnionType(types=types):
            type_dict["types"] = [
                to_dict(
                    type_,
                    clean,
                    alias,
                )
                if isinstance(type_, RecapType)
                else type_
                for type_ in types
            ]
        case ProxyType():
            # Switch `alias` to `type` for ProxyTypes. This is because
            # ProxyType abuses teh "type" attribute to always be "proxy". It
            # uses "alias" as the actual type.
            type_dict["type"] = type_dict.pop("alias")
        case NullType() | BoolType():
            # These types just have a "type" attribute
            pass
        case _:
            type_dict = {"type": "unknown", "description": recap_type.description}
            type_dict.update(recap_type.extra_attrs)

    # Replace concrete type definitions with aliases when possible
    type_dict = alias_dict(type_dict) if alias else type_dict

    # Remove defaults (including non-None defaults)
    type_dict = clean_dict(type_dict) if clean else type_dict

    return type_dict


def clean_dict(type_dict: dict | list | str) -> dict | list | str:
    """
    Remove defaults from a type dictionary, replace unions with lists when
    possible, and replace simple types with strings.

    ```
    {
        "type": "union",
        "types": [
            {
                "type": "int",
                "alias": None,
                "doc": None,
                "logical": None,
                "bits": 32,
                "signed": true,
            },
        ],
    }
    ```

    Would become `[{ "type": "int", "bits": 32}]`

    :param type_dict: A type dictionary, list, or string.
    :return: A cleaner, more compact type dictionary, list, or string.
    """

    if isinstance(type_dict, list):
        type_dict = {
            "type": "union",
            "types": type_dict,
        }
    elif isinstance(type_dict, dict) and "type" not in type_dict:
        raise ValueError(
            "'type' is a required field and was not found in the dictionary."
        )
    elif isinstance(type_dict, str):
        type_dict = {
            "type": type_dict,
        }

    type_name = type_dict.get("type")

    if isinstance(type_name, str):
        recap_type_class = TYPE_CLASSES.get(type_name, ProxyType)
        param_defaults = {}

        # Get defaults from all parent classes
        for cls in recap_type_class.__mro__[:-1]:  # Exclude 'object' class
            sig = inspect.signature(cls.__init__)

            param_defaults.update(
                {
                    # rstrip is for removing '_' from 'bytes_'
                    k.rstrip("_"): v.default
                    for k, v in sig.parameters.items()
                    if v.default is not inspect.Parameter.empty
                }
            )

        # Remove defaults from dictionary
        type_dict = {
            k: v
            for k, v in type_dict.items()
            if k not in param_defaults or param_defaults[k] != v
        }

        if type_name in ("list", "map"):
            assert "values" in type_dict, f"{type_name} must have a 'values' attribute"
            type_dict["values"] = clean_dict(type_dict["values"])

        if type_name == "map":
            type_dict["keys"] = clean_dict(type_dict["keys"])

        if "fields" in type_dict and type_name == "struct":
            type_dict["fields"] = [clean_dict(field) for field in type_dict["fields"]]

        if type_name == "union":
            type_dict["types"] = [clean_dict(t) for t in type_dict["types"]]
    elif isinstance(type_name, list):
        type_dict = {
            "type": "union",
            "types": [clean_dict(t) for t in type_dict["types"]],
        }

    # Support "optional" sytnactic sugar.
    # Shorten {"type": "union", "types": ["null", ...], "default": ...}
    # to {"type": "union", "types": [...], "optional": True}
    if (
        type_dict["type"] == "union"
        and "null" in type_dict["types"]
        and "default" in type_dict
    ):
        # Pop off standard attributes that should be kept whether the type is kept
        # as a union or converted to a single nested type.
        alias = type_dict.pop("alias", None)
        logical = type_dict.pop("logical", None)
        default = type_dict.pop("default")
        doc = type_dict.pop("doc", None)
        name = type_dict.pop("name", None)

        # Only do syntactic sugar if the union is a union with no other
        # (non-standard) extra attributes.
        if len(type_dict) == 2:
            type_dict["types"].remove("null")

            # If the type was ["null", <some type>], use <some type> instead
            # of a union of a single type. Don't do this if union is an alias or
            # logical type, since we promoting the nested type would change what
            # the alias/logical type means.
            if len(type_dict["types"]) == 1 and alias is None and logical is None:
                nested_type = type_dict["types"][0]
                if isinstance(nested_type, str):
                    nested_type = {"type": nested_type}
                type_dict = nested_type
            assert isinstance(type_dict, dict), "Expected type_dict to be a dict."
            attributes = {
                "alias": alias,
                "default": default,
                "doc": doc,
                "logical": logical,
                "name": name,
                "optional": True,
            }
            # Filter None values
            attributes = {k: v for k, v in attributes.items() if v is not None}
            # Add attributes to the type_dict.
            type_dict |= attributes

    # Shorten simple types {"type": "type"} to "type"
    if len(type_dict) == 1:
        return type_dict["type"]

    # Shorten {"type": "union", "types": ["type"]} to ["type"]
    if type_dict["type"] == "union" and len(type_dict) == 2:
        return type_dict["types"]

    if isinstance(type_dict, dict) and type_dict.get("type") == "unknown":
        cleaned_dict = {"type": "unknown"}  # Preserve the type indication
        if "description" in type_dict:
            cleaned_dict["description"] = type_dict["description"]
        return cleaned_dict

    return type_dict


def alias_dict(
    type_dict: dict[str, Any],
    registry: RecapTypeRegistry | None = None,
) -> dict[str, Any]:
    """
    Replaces concrete type definitions with aliases when possible.

    ```
    {
        "type": "int",
        "bits": 32,
        "signed": true,
    }
    ```

    Would become `{"type": "int32"}`.

    :param type_dict: A type dictionary.
    :param registry: A RecapTypeRegistry containing aliases.
    :return: A type dictionary with aliases.
    """

    # Types with a defined alias must always remain as concrete type definitions.
    if type_dict.get("alias") is not None:
        return type_dict

    registry = registry or RecapTypeRegistry()
    recap_type = from_dict(type_dict, registry)

    # If there's a matching alias, replace the type_dict with it
    for alias, alias_type in registry._type_registry.items():
        if recap_type == alias_type:
            return {"type": alias}

    # Otherwise, recurse on nested type_dicts
    for key in ["values", "keys", "fields", "types"]:
        if key in type_dict:
            if isinstance(type_dict[key], list):
                type_dict[key] = [
                    alias_dict(t, registry) if isinstance(t, dict) else t
                    for t in type_dict[key]
                ]
            elif isinstance(type_dict[key], dict):
                type_dict[key] = alias_dict(type_dict[key], registry)

    return type_dict


TYPE_CLASSES = {
    "bool": BoolType,
    "null": NullType,
    "int": IntType,
    "float": FloatType,
    "string": StringType,
    "bytes": BytesType,
    "list": ListType,
    "map": MapType,
    "struct": StructType,
    "enum": EnumType,
    "union": UnionType,
    "unknown": UnknownType,
}


BUILTIN_ALIASES = {
    "int8": IntType(8, signed=True),
    "uint8": IntType(8, signed=False),
    "int16": IntType(16, signed=True),
    "uint16": IntType(16, signed=False),
    "int32": IntType(32, signed=True),
    "uint32": IntType(32, signed=False),
    "int64": IntType(64, signed=True),
    "uint64": IntType(64, signed=False),
    "float16": FloatType(16),
    "float32": FloatType(32),
    "float64": FloatType(64),
    "string32": StringType(bytes_=2_147_483_648, variable=True),
    "string64": StringType(bytes_=9_223_372_036_854_775_807, variable=True),
    "bytes32": BytesType(bytes_=2_147_483_648, variable=True),
    "bytes64": BytesType(bytes_=9_223_372_036_854_775_807, variable=True),
    "uuid": StringType(logical="build.recap.UUID", bytes_=36, variable=False),
    "decimal128": BytesType(
        logical="build.recap.Decimal",
        bytes_=16,
        variable=False,
        precision=28,
        scale=14,
    ),
    "decimal256": BytesType(
        logical="build.recap.Decimal",
        bytes_=32,
        variable=False,
        precision=56,
        scale=28,
    ),
    "duration64": IntType(
        logical="build.recap.Duration",
        bits=64,
        unit="millisecond",
    ),
    "interval128": BytesType(
        logical="build.recap.Interval",
        bytes_=16,
        variable=False,
        unit="millisecond",
    ),
    "time32": IntType(
        logical="build.recap.Time",
        bits=32,
        unit="second",
    ),
    "time64": IntType(
        logical="build.recap.Time",
        bits=64,
        unit="second",
    ),
    "timestamp64": IntType(
        logical="build.recap.Timestamp",
        bits=64,
        unit="millisecond",
        timezone="UTC",
    ),
    "date32": IntType(
        logical="build.recap.Date",
        bits=32,
        unit="day",
    ),
    "date64": IntType(
        logical="build.recap.Date",
        bits=64,
        unit="day",
    ),
}
