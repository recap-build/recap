from proto_schema_parser.ast import (
    Enum,
    EnumElement,
    EnumValue,
    Field,
    FieldCardinality,
    File,
    MapField,
    Message,
    MessageElement,
    OneOf,
    Package,
)
from proto_schema_parser.parser import Parser

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

DEFAULT_NAMESPACE = "_root"
"""
Namespace to use when no namespace is specified in the schema.
"""


class ProtobufConverter:
    def __init__(self, namespace: str = DEFAULT_NAMESPACE) -> None:
        self.namespaces = [namespace]
        self.registry = RecapTypeRegistry()

    def to_recap(
        self,
        protobuf_schema_str: str,
    ) -> StructType:
        file = Parser().parse(protobuf_schema_str)
        root_message = self._parse(file)
        root_message = self._resolve_proxies(root_message)

        if not isinstance(root_message, StructType):
            raise ValueError("Protobuf schema must be a Message")

        return root_message

    def _resolve_proxies(
        self,
        recap_type: RecapType,
        resolved: set[str] | None = None,
        seen: set[str] | None = None,
    ) -> RecapType:
        resolved = resolved or set()
        seen = seen or set()

        # Detect circular references.
        if not isinstance(recap_type, ProxyType) and recap_type.alias is not None:
            seen.add(recap_type.alias)

        if (
            isinstance(recap_type, ProxyType)
            # Skip if already resolved.
            and recap_type.alias not in resolved
            # Skip if circular reference.
            and recap_type.alias not in seen
        ):
            extra_attrs = recap_type.extra_attrs
            alias = recap_type.alias
            recap_type = recap_type.resolve()
            recap_type.alias = alias
            recap_type.extra_attrs |= extra_attrs
            resolved.add(recap_type.alias)  # pyright: ignore[reportGeneralTypeIssues]

        if isinstance(recap_type, ListType):
            recap_type.values = self._resolve_proxies(recap_type.values, resolved, seen)
        elif isinstance(recap_type, MapType):
            recap_type.keys = self._resolve_proxies(recap_type.keys, resolved, seen)
            recap_type.values = self._resolve_proxies(recap_type.values, resolved, seen)
        elif isinstance(recap_type, UnionType):
            recap_type.types = [
                self._resolve_proxies(t, resolved, seen) for t in recap_type.types
            ]
        elif isinstance(recap_type, StructType):
            recap_type.fields = [
                self._resolve_proxies(f, resolved, seen) for f in recap_type.fields
            ]

        return recap_type

    def _parse(self, file: File) -> StructType:
        root_message = None

        # Find the namespace first, since we need it for message and enum aliases.
        packages = [p for p in file.file_elements if isinstance(p, Package)]

        if packages:
            self.namespaces.append(packages[0].name)

        # Now parse messages and enums.
        for file_element in file.file_elements:
            if isinstance(file_element, Message):
                struct_type = self._parse_message(file_element)
                root_message = root_message or struct_type
            elif isinstance(file_element, Enum):
                self._parse_enum(file_element)

        if root_message is None:
            raise ValueError("Protobuf schema must contain at least one Message")

        self.namespaces.pop()

        return root_message

    def _parse_message(self, message: Message) -> StructType:
        fields = []

        for element in message.elements:
            if isinstance(element, Field):
                recap_type = self._parse_field(element)
                fields.append(recap_type)
            elif isinstance(element, MapField):
                recap_type = self._parse_map_field(element)
                fields.append(recap_type)
            elif isinstance(element, OneOf):
                recap_type = self._parse_oneof(element)
                fields.append(recap_type)
            elif isinstance(element, Message):
                self._parse_message(element)
            elif isinstance(element, Enum):
                self._parse_enum(element)

        struct_type = StructType(
            fields=fields,
            alias=f"{self.namespaces[-1]}.{message.name}",
        )

        self.registry.register_alias(struct_type)

        return struct_type

    def _parse_field(self, field: Field) -> RecapType:
        recap_type = self._protobuf_type_to_recap_type(field.type)

        if field.cardinality == FieldCardinality.REPEATED:
            recap_type = ListType(values=recap_type)

        if field.cardinality != FieldCardinality.REQUIRED:
            if not isinstance(recap_type, NullType):
                recap_type = UnionType(types=[NullType(), recap_type], default=None)
            recap_type.extra_attrs["default"] = None

        recap_type.extra_attrs["name"] = field.name

        return recap_type

    def _parse_map_field(self, field: MapField) -> RecapType:
        key_type = self._protobuf_type_to_recap_type(field.key_type)

        # Proto map keys are always strings or integers.
        assert isinstance(key_type, IntType) or isinstance(key_type, StringType)

        value_type = self._protobuf_type_to_recap_type(field.value_type)
        map_type = UnionType(
            types=[
                NullType(),
                MapType(keys=key_type, values=value_type),
            ],
            default=None,
        )

        if field.name is not None:
            map_type.extra_attrs["name"] = field.name

        return map_type

    def _protobuf_type_to_recap_type(self, protobuf_type: str) -> RecapType:
        # NOTE: Protobuf doesn't support type aliases, so we don't need to
        # register aliases here (or in oneof, map, etc).
        match protobuf_type:
            case "string":
                return StringType(bytes_=2_147_483_648, variable=True)
            case "bool":
                return BoolType()
            case "bytes":
                return BytesType(bytes_=2_147_483_648, variable=True)
            case "int32":
                return IntType(bits=32)
            case "int64":
                return IntType(bits=64)
            case "uint32":
                return IntType(bits=32, signed=False)
            case "uint64":
                return IntType(bits=64, signed=False)
            case "sint32":
                return IntType(bits=32)
            case "sint64":
                return IntType(bits=64)
            case "float":
                return FloatType(bits=32)
            case "double":
                return FloatType(bits=64)
            case "fixed32":
                return IntType(bits=32, signed=False)
            case "fixed64":
                return IntType(bits=64, signed=False)
            case "sfixed32":
                return IntType(bits=32)
            case "sfixed64":
                return IntType(bits=64)
            # Handle some of Google's well-known types.
            # Technically, we should honor `import google/protobuf/*.proto` and
            # make sure the protos match what's expected, but assuming they match
            # is fine for now.
            case "google.protobuf.Timestamp":
                # https://protobuf.dev/reference/protobuf/google.protobuf/#timestamp
                # Note: Some protobuf values might overrun this since they support
                # from 0001-01-01T00:00:00Z to 9999-12-31T23:59:59.999999999Z.
                return IntType(
                    logical="build.recap.Timestamp",
                    bits=64,
                    signed=True,
                    unit="nanosecond",
                    timezone="UTC",
                )
            case "google.protobuf.Duration":
                # https://protobuf.dev/reference/protobuf/google.protobuf/#duration
                # Note: Some protobuf values might overrun this since they support
                # int64 seconds and int32 nanoseconds.
                return IntType(
                    bits=64,
                    logical="build.recap.Duration",
                    unit="nanosecond",
                )
            case "google.protobuf.NullValue":
                return NullType()
            case _:
                # Create a ProxyType and hope we have a type alias for this type.
                alias = (
                    protobuf_type
                    if "." in protobuf_type
                    else f"{self.namespaces[-1]}.{protobuf_type}"
                )
                return ProxyType(alias, self.registry)

    def _parse_oneof(self, oneof: OneOf) -> RecapType:
        types: list[RecapType] = [NullType()]
        for element in oneof.elements:
            if isinstance(element, Field):
                # !! HACK !!
                # Force oneof subfield to be required since we're unioning with null above.
                # Otherwise we end up with [NullType, [NullType, RecapType], ...].
                # This is safe to force because oneof subfields can't be repeated.
                original_cardinality = element.cardinality
                element.cardinality = FieldCardinality.REQUIRED
                recap_type = self._parse_field(element)
                element.cardinality = original_cardinality
                types.append(recap_type)
        return UnionType(types=types, name=oneof.name, default=None)

    def _parse_enum(self, enum: Enum) -> RecapType:
        symbols = []
        for element in enum.elements:
            if isinstance(element, EnumValue):
                symbols.append(element.name)
        enum_type = EnumType(
            symbols=symbols,
            alias=f"{self.namespaces[-1]}.{enum.name}",
        )
        self.registry.register_alias(enum_type)
        return enum_type

    def from_recap(self, struct_type: StructType) -> File:
        """Convert a Recap type to a Protobuf type."""
        assert struct_type.alias is not None, "Struct must have an alias."
        package_to_types: dict[str, list[Message | Enum]] = {}
        self._from_recap_gather_types(struct_type, package_to_types)
        # Lexicographical sort always puts the root package first.
        package = sorted(package_to_types.keys())[0]
        # Verify all subpackages are under the root package.
        for subpackage in package_to_types.keys():
            assert subpackage.startswith(package), (
                "Proto files must contain messages in a single root package space, "
                f"but found root={package} and subpackage={subpackage}."
            )
        return File(
            file_elements=[Package(name=package)]
            + self._from_recap_construct_elements(package, package_to_types)  # type: ignore
        )

    def _from_recap_gather_types(
        self,
        recap_type: RecapType,
        package_to_types: dict[str, list[Message | Enum]],
    ) -> None:
        """
        Find all Message and Enum types that need to be declared in the proto
        file. Keep track of their package so we can construct the proto file
        with the correct nesting.

        :param recap_type: The Recap type to convert.
        :param package_to_types: A mapping of package to types that have been
            discovered.
        """

        match recap_type:
            case StructType(fields=fields):
                assert recap_type.alias is not None, "Struct must have an alias."
                assert "." in recap_type.alias, "Alias must have dotted package."
                package, message_name = recap_type.alias.rsplit(".", 1)
                field_number = 1
                message_elements: list[MessageElement] = []

                for field in recap_type.fields:
                    message_elements.append(
                        self._recap_to_field(field, field_number, package)
                    )
                    field_number += 1
                    self._from_recap_gather_types(field, package_to_types)

                package_to_types.setdefault(package, []).append(
                    Message(
                        message_name,
                        message_elements,
                    )
                )
            case UnionType(types=types):
                for type_ in types:
                    self._from_recap_gather_types(type_, package_to_types)
            case MapType(keys=keys, values=values):
                self._from_recap_gather_types(keys, package_to_types)
                self._from_recap_gather_types(values, package_to_types)
            case ListType(values=values):
                self._from_recap_gather_types(values, package_to_types)
            case EnumType(symbols=symbols):
                assert recap_type.alias is not None, "Enum must have an alias."
                enum_package, enum_name = recap_type.alias.rsplit(".", 1)
                elements: list[EnumElement] = [
                    EnumValue(symbol, idx)
                    for symbol, idx in zip(
                        recap_type.symbols, range(len(recap_type.symbols))
                    )
                ]
                enum = Enum(enum_name, elements)
                package_to_types.setdefault(enum_package, []).append(enum)

    def _from_recap_construct_elements(
        self,
        package: str,
        package_to_types: dict[str, list[Message | Enum]],
    ) -> list[Message | Enum]:
        """
        Construct the proto file elements for a given package. This method
        mutates the existing Message/Enum structures to contain nested
        elements.

        :param package: The package to construct elements for.
        :param package_to_types: A mapping of package to types that have been
            discovered.
        :return: The proto FileElements (or MessageElements) for the package.
        """

        package_types = package_to_types.get(package, [])
        for package_type in package_types:
            if isinstance(package_type, Message):
                subelements = self._from_recap_construct_elements(
                    f"{package}.{package_type.name}",
                    package_to_types,
                )
                package_type.elements.extend(subelements)
        return package_types

    def _recap_to_field(
        self,
        recap_type: RecapType,
        field_number: int,
        package: str,
    ) -> Field | MapField | OneOf:
        """
        Convert a Recap type to a Protobuf field. This method is recursive and
        will call itself for nested types.

        :param recap_type: The Recap type to convert.
        :param field_number: The field number to assign to the field.
        :param package: The package of the field.
        :return: The Protobuf field.
        """

        field_name = recap_type.extra_attrs.get("name", f"field_{field_number}")
        match recap_type:
            case NullType():
                return Field(field_name, field_number, "google.protobuf.NullValue")
            case BoolType():
                return Field(field_name, field_number, "bool")
            case IntType(signed=bool(signed), bits=int(bits)) if signed and bits <= 32:
                return Field(field_name, field_number, "int32")
            case IntType(signed=bool(signed), bits=int(bits)) if signed and bits <= 64:
                return Field(field_name, field_number, "int64")
            case IntType(
                signed=bool(signed), bits=int(bits)
            ) if not signed and bits <= 32:
                return Field(field_name, field_number, "uint32")
            case IntType(
                signed=bool(signed), bits=int(bits)
            ) if not signed and bits <= 64:
                return Field(field_name, field_number, "uint64")
            case IntType():
                raise ValueError(
                    "Invalid bit size for IntType. Protobuf supports only 32 "
                    "or 64 bits for integer types."
                )
            case FloatType(bits=int(bits)) if bits <= 32:
                return Field(field_name, field_number, "float")
            case FloatType(bits=int(bits)) if bits <= 64:
                return Field(field_name, field_number, "double")
            case FloatType():
                raise ValueError(
                    "Invalid bit size for FloatType. Protobuf supports only 32 "
                    "or 64 bits for floating-point types."
                )
            case StringType(bytes_=int(bytes_)) if bytes_ <= 2_147_483_647:
                return Field(field_name, field_number, "string")
            case BytesType(bytes_=int(bytes_)) if bytes_ <= 2_147_483_647:
                return Field(field_name, field_number, "bytes")
            case ListType(values=values):
                nested_field = self._recap_to_field(values, field_number, package)
                assert isinstance(
                    nested_field,
                    Field,
                ), "Maps and unions can't be repeated (lists)."
                nested_field.cardinality = FieldCardinality.REPEATED
                return nested_field
            case MapType(keys=keys, values=values):
                # 0 field_number because we ignore it. We just need types.
                key_field = self._recap_to_field(keys, 0, package)
                value_field = self._recap_to_field(values, 0, package)
                assert isinstance(
                    key_field, Field
                ), "Key must be integral or string type."
                assert isinstance(value_field, Field), "Value must not be a map type."
                return MapField(
                    field_name,
                    field_number,
                    key_field.type,
                    value_field.type,
                )
            case UnionType(types=types):
                non_null_types = [t for t in types if not isinstance(t, NullType)]
                if len(non_null_types) == 1:
                    # One non-null type means this is a nullable field.
                    field = self._recap_to_field(
                        non_null_types[0],
                        field_number,
                        package,
                    )
                    assert isinstance(field, Field), "Maps can't be nullable."
                    field.cardinality = FieldCardinality.OPTIONAL
                    return field
                else:
                    # Multiple non-null types means this is a true union of multiple types.
                    oneof_field_num = field_number
                    oneof_fields = []
                    # OneOf fields are always optional, so no need to include NullType.
                    for non_null_type in non_null_types:
                        field = self._recap_to_field(
                            non_null_type,
                            oneof_field_num,
                            package,
                        )
                        oneof_fields.append(field)
                        oneof_field_num += 1
                    return OneOf(field_name, oneof_fields)
            case (
                StructType(alias=alias) | EnumType(alias=alias) | ProxyType(alias=alias)
            ):
                assert alias is not None, "Expected alias to be set."
                # Always start from the root since Recap namespaces are always root-based.
                return Field(field_name, field_number, "." + alias)
            case _:
                return UnknownType()
