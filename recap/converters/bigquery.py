from __future__ import annotations

from google.cloud import bigquery

from recap.types import (
    BoolType,
    BytesType,
    FloatType,
    IntType,
    ListType,
    StringType,
    StructType,
    UnknownType,
)


class BigQueryConverter:
    def to_recap(self, fields: list[bigquery.SchemaField]) -> StructType:
        recap_fields = []
        for field in fields:
            match field.field_type:
                case "STRING" | "JSON":
                    # I'm having a hard time finding the max string length in BQ. This link:
                    # https://cloud.google.com/bigquery/docs/reference/standard-sql/data-types
                    # Says "2 logical bytes + the UTF-8 encoded string size", so I'm assuming
                    # the 2 logical bytes are a uint16 length header, which is 65_536.
                    field_type = StringType(bytes_=field.max_length)
                case "BYTES":
                    field_type = BytesType(bytes_=field.max_length)
                case "INT64" | "INTEGER" | "INT" | "SMALLINT" | "TINYINT" | "BYTEINT":
                    field_type = IntType(bits=64)
                case "FLOAT" | "FLOAT64":
                    field_type = FloatType(bits=64)
                case "BOOLEAN":
                    field_type = BoolType()
                case "TIMESTAMP" | "DATETIME":
                    field_type = IntType(
                        logical="build.recap.Timestamp",
                        bits=64,
                        unit="microsecond",
                    )
                case "TIME":
                    field_type = IntType(
                        logical="build.recap.Time",
                        bits=32,
                        unit="microsecond",
                    )
                case "DATE":
                    field_type = IntType(
                        logical="build.recap.Date",
                        bits=32,
                        unit="day",
                    )
                case "RECORD" | "STRUCT":
                    field_type = self.to_recap(list(field.fields))
                case "NUMERIC" | "DECIMAL":
                    field_type = BytesType(
                        logical="build.recap.Decimal",
                        bytes_=16,
                        variable=False,
                        precision=field.precision or 38,
                        scale=field.scale or 0,
                    )
                case "BIGNUMERIC" | "BIGDECIMAL":
                    field_type = BytesType(
                        logical="build.recap.Decimal",
                        bytes_=32,
                        variable=False,
                        precision=field.precision or 76,
                        scale=field.scale or 0,
                    )
                case _:
                    field_type = UnknownType()

            if field.mode == "REPEATED":
                field_type = ListType(field_type)
            if field.mode == "NULLABLE":
                field_type = field_type.make_nullable()
            if name := field.name:
                field_type.extra_attrs["name"] = name
            if description := field.description:
                field_type.doc = description
            if default := field.default_value_expression:
                field_type.extra_attrs["default"] = default

            recap_fields.append(field_type)

        return StructType(recap_fields)
