from __future__ import annotations

from pymetastore.htypes import (
    HCharType,
    HDecimalType,
    HListType,
    HMapType,
    HPrimitiveType,
    HStructType,
    HType,
    HUnionType,
    HVarcharType,
    PrimitiveCategory,
)
from pymetastore.metastore import HColumn, HTable

from recap.types import (
    BoolType,
    BytesType,
    FloatType,
    IntType,
    ListType,
    MapType,
    NullType,
    RecapType,
    StringType,
    StructType,
    UnionType,
    UnknownType,
)


class HiveMetastoreConverter:
    def to_recap(
        self,
        table: HTable,
    ) -> StructType:
        fields: list[RecapType] = []
        for col in table.columns:
            recap_type = self._parse_schema(col)
            fields.append(recap_type)
        return StructType(fields=fields, name=table.name)

    def _parse_schema(self, htype: HType | HColumn) -> RecapType:
        recap_type: RecapType | None = None
        extra_attrs = {}
        if isinstance(htype, HColumn):
            extra_attrs["name"] = htype.name
            if htype.comment:
                extra_attrs["doc"] = htype.comment
            htype = htype.type
        match htype:
            case HPrimitiveType(primitive_type=PrimitiveCategory.BOOLEAN):
                recap_type = BoolType(**extra_attrs)
            case HPrimitiveType(primitive_type=PrimitiveCategory.BYTE):
                recap_type = IntType(bits=8, **extra_attrs)
            case HPrimitiveType(primitive_type=PrimitiveCategory.SHORT):
                recap_type = IntType(bits=16, **extra_attrs)
            case HPrimitiveType(primitive_type=PrimitiveCategory.INT):
                recap_type = IntType(bits=32, **extra_attrs)
            case HPrimitiveType(primitive_type=PrimitiveCategory.LONG):
                recap_type = IntType(bits=64, **extra_attrs)
            case HPrimitiveType(primitive_type=PrimitiveCategory.FLOAT):
                recap_type = FloatType(bits=32, **extra_attrs)
            case HPrimitiveType(primitive_type=PrimitiveCategory.DOUBLE):
                recap_type = FloatType(bits=64, **extra_attrs)
            case HPrimitiveType(primitive_type=PrimitiveCategory.VOID):
                recap_type = NullType(**extra_attrs)
            case HPrimitiveType(primitive_type=PrimitiveCategory.STRING):
                # TODO: Should handle multi-byte encodings
                recap_type = StringType(**extra_attrs)
            case HPrimitiveType(primitive_type=PrimitiveCategory.BINARY):
                recap_type = BytesType(bytes_=2_147_483_647, **extra_attrs)
            case HDecimalType(precision=int(precision), scale=int(scale)):
                # TODO: Decimals can be > 38 digits, but need to calculate bytes_.
                if precision > 38:
                    raise ValueError(f"Max decimal precision is 38, got {precision}")
                recap_type = BytesType(
                    logical="build.recap.Decimal",
                    bytes_=16,
                    variable=False,
                    precision=precision,
                    scale=scale,
                    **extra_attrs,
                )
            case HVarcharType(length=int(length)):
                # TODO: Should handle multi-byte encodings
                recap_type = StringType(bytes_=length, **extra_attrs)
            case HCharType(length=int(length)):
                # TODO: Should handle multi-byte encodings
                recap_type = StringType(bytes_=length, variable=False, **extra_attrs)
            case HPrimitiveType(primitive_type=PrimitiveCategory.DATE):
                recap_type = IntType(
                    logical="build.recap.Date",
                    bits=32,
                    signed=True,
                    unit="day",
                    **extra_attrs,
                )
            case HPrimitiveType(primitive_type=PrimitiveCategory.TIMESTAMP):
                # Hive stores timestamps as strings, so 64 bits isn't enough to store
                # all possible values. C'est la vie.
                recap_type = IntType(
                    logical="build.recap.Timestamp",
                    bits=64,
                    signed=True,
                    unit="nanosecond",
                    timezone="UTC",
                    **extra_attrs,
                )
            case HPrimitiveType(primitive_type=PrimitiveCategory.TIMESTAMPLOCALTZ):
                # Hive stores timestamps as strings, so 64 bits isn't enough to store
                # all possible values. C'est la vie.
                recap_type = IntType(
                    logical="build.recap.Timestamp",
                    bits=64,
                    signed=True,
                    unit="nanosecond",
                    # Follow Apache Arrow's Schema.fbs style for local time.
                    # Denote LOCALTZ as a timezone field set to None.
                    timezone=None,
                    **extra_attrs,
                )
            case HPrimitiveType(primitive_type=PrimitiveCategory.INTERVAL_YEAR_MONTH):
                recap_type = BytesType(
                    logical="build.recap.Interval",
                    bytes_=12,
                    signed=True,
                    unit="month",
                    **extra_attrs,
                )
            case HPrimitiveType(primitive_type=PrimitiveCategory.INTERVAL_DAY_TIME):
                recap_type = BytesType(
                    logical="build.recap.Interval",
                    bytes_=12,
                    signed=True,
                    unit="second",
                    **extra_attrs,
                )
            case HMapType(key_type=key_type, value_type=value_type):
                recap_type = MapType(
                    keys=self._parse_schema(key_type),
                    values=self._parse_schema(value_type),
                    **extra_attrs,
                )
            case HListType(element_type=element_type):
                recap_type = ListType(
                    values=self._parse_schema(element_type),
                    **extra_attrs,
                )
            case HUnionType(types=types):
                # Hive columns are always nullable and default is always null.
                types = [NullType()] + [self._parse_schema(t) for t in htype.types]
                recap_type = UnionType(types=types, default=None, **extra_attrs)
                recap_type = self._flatten_unions(recap_type)
            case HStructType(names=names, types=types):
                recap_type = StructType(
                    fields=[
                        self._parse_schema(HColumn(n, t)) for n, t in zip(names, types)
                    ],
                    **extra_attrs,
                )
            case _:
                recap_type = UnknownType(**extra_attrs)

        if not isinstance(recap_type, UnionType) and not isinstance(
            recap_type,
            NullType,
        ):
            recap_type = recap_type.make_nullable()

        return recap_type

    def _flatten_unions(self, recap_type: RecapType) -> RecapType:
        """
        Flattens nested unions into a single union. Useful for unwinding a
        HUnionType since we're wrapping all fields in _parse_schema() in a
        union. Without this, we'd get [NullType, [NullType, IntType],
        [NullType, StrType], ...]. Now we get [NullType, IntType, StrType].
        """

        extra_attrs = recap_type.extra_attrs | {
            "logical": recap_type.logical,
            "alias": recap_type.alias,
            "doc": recap_type.doc,
        }

        if isinstance(recap_type, UnionType):
            # Start with empty set of flattened types
            flattened_types = []

            for union_subtype in recap_type.types:
                # We're not expecting string type aliases here.
                assert isinstance(union_subtype, RecapType)

                # Recursively flatten unions within unions
                flattened = self._flatten_unions(union_subtype)

                if isinstance(flattened, UnionType):
                    # Append types from inner union to the flattened types
                    flattened_types.extend(
                        [t for t in flattened.types if t not in flattened_types]
                    )
                elif flattened not in flattened_types:
                    # Append non-union types directly
                    flattened_types.append(flattened)

            return UnionType(
                types=flattened_types,
                **extra_attrs,
            )
        elif isinstance(recap_type, StructType):
            return StructType(
                fields=[self._flatten_unions(field) for field in recap_type.fields],
                **extra_attrs,
            )
        elif isinstance(recap_type, ListType):
            return ListType(
                values=self._flatten_unions(recap_type.values),
                extra_attrs=extra_attrs,
            )
        elif isinstance(recap_type, MapType):
            return MapType(
                keys=self._flatten_unions(recap_type.keys),
                values=self._flatten_unions(recap_type.values),
                extra_attrs=extra_attrs,
            )
        else:
            # No nested union type to flatten
            return recap_type
