from math import ceil
from typing import Any

from recap.converters.dbapi import DbapiConverter
from recap.types import (
    BoolType,
    BytesType,
    EnumType,
    FloatType,
    IntType,
    ListType,
    NullType,
    ProxyType,
    RecapType,
    RecapTypeRegistry,
    StringType,
    UnionType,
    UnknownType,
)

MAX_FIELD_SIZE = 1073741824

DEFAULT_NAMESPACE = "_root"
"""
Namespace to use when no namespace is specified in the schema.
"""


class PostgresqlConverter(DbapiConverter):
    def __init__(
        self,
        enforce_array_dimensions: bool = False,
        namespace: str = DEFAULT_NAMESPACE,
    ):
        # since array dimensionality is not enforced by PG schemas:
        #   if `enforce_array_dimensions = False` then read arrays irrespective of how many dimensions they have
        #   if `enforce_array_dimensions = True` then read arrays as nested lists
        self.enforce_array_dimensions = enforce_array_dimensions
        self.namespace = namespace
        self.registry = RecapTypeRegistry()

    def _parse_type(self, column_props: dict[str, Any]) -> RecapType:
        column_name = column_props["COLUMN_NAME"]
        data_type = column_props["DATA_TYPE"].lower()
        octet_length = column_props["CHARACTER_OCTET_LENGTH"]
        max_length = column_props["CHARACTER_MAXIMUM_LENGTH"]
        udt_name = (column_props["UDT_NAME"] or "").lower()
        ndims = column_props["ATTNDIMS"]

        if data_type in ["bigint", "int8", "bigserial", "serial8"]:
            base_type = IntType(bits=64, signed=True)
        elif data_type in ["integer", "int", "int4", "serial", "serial4"]:
            base_type = IntType(bits=32, signed=True)
        elif data_type in ["smallint", "smallserial", "serial2"]:
            base_type = IntType(bits=16, signed=True)
        elif data_type in ["double precision", "float8"]:
            base_type = FloatType(bits=64)
        elif data_type in ["real", "float4"]:
            base_type = FloatType(bits=32)
        elif data_type == "boolean":
            base_type = BoolType()
        elif (
            data_type in ["text", "json", "jsonb"]
            or data_type.startswith("character varying")
            or data_type.startswith("varchar")
        ):
            base_type = StringType(bytes_=octet_length, variable=True)
        elif data_type.startswith("char"):
            base_type = StringType(bytes_=octet_length, variable=False)
        elif data_type == "uuid":
            base_type = StringType(
                logical="build.recap.UUID",
                bytes_=36,
                variable=False,
            )
        elif data_type == "bytea" or data_type.startswith("bit varying"):
            base_type = BytesType(bytes_=MAX_FIELD_SIZE, variable=True)
        elif data_type.startswith("bit"):
            byte_length = ceil(max_length / 8)
            base_type = BytesType(bytes_=byte_length, variable=False)
        elif data_type.startswith("timestamp"):
            dt_precision = column_props["DATETIME_PRECISION"]
            unit = self._get_time_unit([dt_precision]) or "microsecond"
            base_type = IntType(
                bits=64,
                logical="build.recap.Timestamp",
                unit=unit,
            )
        elif data_type.startswith("decimal") or data_type.startswith("numeric"):
            base_type = BytesType(
                logical="build.recap.Decimal",
                bytes_=32,
                variable=False,
                precision=column_props["NUMERIC_PRECISION"],
                scale=column_props["NUMERIC_SCALE"],
            )
        elif data_type == "array":
            # Remove _ for standard PG types like _int4
            nested_data_type = udt_name.lstrip("_")
            # Recurse to get the array value type (the int4 in int4[])
            # Postgres arrays ignore value type octet lengths for varchars, bit
            # lengths, etc. Thus, we only set DATA_TYPE here. Sigh.
            value_type = self._parse_type(
                {
                    "COLUMN_NAME": None,
                    "DATA_TYPE": nested_data_type,
                    # Default strings, bits, etc. to the max field size since
                    # information_schema doesn't contain lengths for array
                    # types.
                    # TODO Technically, we could consult pg_attribute and
                    # pg_type for this information, but that's not implemented
                    # right now.
                    "CHARACTER_OCTET_LENGTH": MAX_FIELD_SIZE,
                    # * 8 because bit columns use bits not bytes.
                    "CHARACTER_MAXIMUM_LENGTH": MAX_FIELD_SIZE * 8,
                    "UDT_NAME": None,
                    "ATTNDIMS": 0,
                }
            )
            if self.enforce_array_dimensions:
                base_type = self._create_n_dimension_list(value_type, ndims)
            else:
                column_name_without_periods = column_name.replace(".", "_")
                base_type_alias = f"{self.namespace}.{column_name_without_periods}"
                # Construct a self-referencing list comprised of the array's value
                # type and a proxy to the list itself. This allows arrays to be an
                # arbitrary number of dimensions, which is how PostgreSQL treats
                # lists. See https://github.com/recap-build/recap/issues/264 for
                # more details.
                base_type = ListType(
                    alias=base_type_alias,
                    values=UnionType(
                        types=[
                            value_type,
                            ProxyType(
                                alias=base_type_alias,
                                registry=self.registry,
                            ),
                        ],
                    ),
                )
                self.registry.register_alias(base_type)
        elif data_type == "user-defined" and column_props["ENUM_VALUES"]:
            base_type = EnumType(
                symbols=column_props["ENUM_VALUES"],
            )
        else:
            base_type = UnknownType()

        return base_type

    def _create_n_dimension_list(self, base_type: RecapType, ndims: int) -> RecapType:
        """
        Build a list type with `ndims` dimensions containing nullable `base_type` as the innermost value type.
        """
        if ndims == 0:
            return UnionType(types=[NullType(), base_type])
        else:
            return ListType(
                values=self._create_n_dimension_list(base_type, ndims - 1),
            )
