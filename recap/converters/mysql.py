from typing import Any

from recap.converters.dbapi import DbapiConverter
from recap.types import BytesType, FloatType, IntType, RecapType, StringType, UnknownType


class MysqlConverter(DbapiConverter):
    def _parse_type(self, column_props: dict[str, Any]) -> RecapType:
        data_type = column_props["DATA_TYPE"].lower()
        octet_length = column_props["CHARACTER_OCTET_LENGTH"]
        precision = column_props["NUMERIC_PRECISION"]
        scale = column_props["NUMERIC_SCALE"]

        if data_type == "bigint":
            # https://dev.mysql.com/doc/refman/8.0/en/integer-types.html
            base_type = IntType(bits=64, signed=True)
        elif data_type in ["int", "integer"]:
            # https://dev.mysql.com/doc/refman/8.0/en/integer-types.html
            base_type = IntType(bits=32, signed=True)
        elif data_type == "mediumint":
            # https://dev.mysql.com/doc/refman/8.0/en/integer-types.html
            base_type = IntType(bits=24, signed=True)
        elif data_type == "smallint":
            # https://dev.mysql.com/doc/refman/8.0/en/integer-types.html
            base_type = IntType(bits=16, signed=True)
        elif data_type == "tinyint":
            # https://dev.mysql.com/doc/refman/8.0/en/integer-types.html
            base_type = IntType(bits=8, signed=True)
        elif data_type == "double" or (data_type == "float" and precision > 23):
            # https://dev.mysql.com/doc/refman/8.0/en/floating-point-types.html
            base_type = FloatType(bits=64)
        elif data_type == "float" and precision <= 23:
            # https://dev.mysql.com/doc/refman/8.0/en/floating-point-types.html
            base_type = FloatType(bits=32)
        elif data_type in [
            "text",
            "json",
            "mediumtext",
            "longtext",
            "tinytext",
        ] or data_type.startswith("varchar"):
            # This isn't exactly correct for JSON. MySQL uses a binary encoding
            # to store the structure.
            base_type = StringType(bytes_=octet_length, variable=True)
        elif data_type.startswith("char") or data_type in ["enum", "set"]:
            base_type = StringType(bytes_=octet_length, variable=False)
        elif data_type in [
            "blob",
            "mediumblob",
            "longblob",
            "tinyblob",
        ] or data_type.startswith("varbinary"):
            base_type = BytesType(bytes_=octet_length, variable=True)
        elif data_type.startswith("binary"):
            base_type = BytesType(bytes_=octet_length, variable=False)
        elif data_type.startswith("bit"):
            base_type = BytesType(bytes_=8, variable=False)
        elif data_type.startswith("timestamp") or data_type.startswith("datetime"):
            dt_precision = column_props["DATETIME_PRECISION"]
            unit = self._get_time_unit([dt_precision]) or "microsecond"
            base_type = IntType(
                bits=64,
                logical="build.recap.Timestamp",
                unit=unit,
            )
        elif data_type in ["dec", "decimal", "numeric"]:
            base_type = BytesType(
                logical="build.recap.Decimal",
                bytes_=32,
                variable=False,
                precision=precision,
                scale=scale,
            )
        elif data_type == "year":
            base_type = IntType(
                bits=16,
                signed=False,
            )  # Years are typically 2-byte values
        else:
            base_type = UnknownType()

        return base_type
