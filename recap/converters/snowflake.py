from typing import Any

from recap.converters.dbapi import DbapiConverter
from recap.types import BoolType, BytesType, FloatType, IntType, RecapType, StringType, UnknownType


class SnowflakeConverter(DbapiConverter):
    def _parse_type(self, column_props: dict[str, Any]) -> RecapType:
        data_type = column_props["DATA_TYPE"].lower()
        octet_length = column_props["CHARACTER_OCTET_LENGTH"]

        if data_type in [
            "float",
            "float4",
            "float8",
            "double",
            "double precision",
            "real",
        ]:
            base_type = FloatType(bits=64)
        elif data_type == "boolean":
            base_type = BoolType()
        elif data_type in [
            "number",
            "decimal",
            "numeric",
            "int",
            "integer",
            "bigint",
            "smallint",
            "tinyint",
            "byteint",
        ] or (
            data_type.startswith("number")
            or data_type.startswith("decimal")
            or data_type.startswith("numeric")
        ):
            base_type = BytesType(
                logical="build.recap.Decimal",
                bytes_=16,
                variable=False,
                precision=column_props["NUMERIC_PRECISION"] or 38,
                scale=column_props["NUMERIC_SCALE"] or 0,
            )
        elif (
            data_type.startswith("varchar")
            or data_type.startswith("string")
            or data_type.startswith("text")
            or data_type.startswith("nvarchar")
            or data_type.startswith("nvarchar2")
            or data_type.startswith("char varying")
            or data_type.startswith("nchar varying")
        ):
            base_type = StringType(bytes_=octet_length or 16_777_216, variable=True)
        elif (
            data_type.startswith("char")
            or data_type.startswith("nchar")
            or data_type.startswith("character")
        ):
            base_type = StringType(bytes_=octet_length or 1, variable=True)
        elif data_type in ["binary", "varbinary", "blob"]:
            base_type = BytesType(bytes_=octet_length or 8_388_608)
        elif data_type == "date":
            base_type = IntType(bits=32, logical="build.recap.Date", unit="day")
        elif data_type.startswith("timestamp") or data_type.startswith("datetime"):
            params = self._parse_parameters(data_type)
            unit = self._get_time_unit(params) or "nanosecond"
            base_type = IntType(
                bits=64,
                logical="build.recap.Timestamp",
                unit=unit,
            )
        elif data_type.startswith("time"):
            params = self._parse_parameters(data_type)
            unit = self._get_time_unit(params) or "nanosecond"
            base_type = IntType(bits=32, logical="build.recap.Time", unit=unit)
        else:
            base_type = UnknownType()

        return base_type
