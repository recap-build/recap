from enum import Enum
from typing import Any

from recap.converters.dbapi import DbapiConverter
from recap.types import (
    BytesType,
    FloatType,
    IntType,
    NullType,
    RecapType,
    StringType,
    UnionType,
    UnknownType,
)

# SQLite's maximum length is 2^31-1 bytes, or 2147483647 bytes.
SQLITE_MAX_LENGTH = 2147483647


class SQLiteAffinity(Enum):
    """
    SQLite uses column affinity to map non-STRICT table columns to values. See
    https://www.sqlite.org/datatype3.html#type_affinity for details.
    """

    INTEGER = "integer"
    REAL = "real"
    TEXT = "text"
    BLOB = "blob"
    NUMERIC = "numeric"


class SQLiteConverter(DbapiConverter):
    def _parse_type(self, column_props: dict[str, Any]) -> RecapType:
        column_name = column_props["COLUMN_NAME"]
        column_type = column_props["TYPE"]
        octet_length = column_props["CHARACTER_OCTET_LENGTH"]
        precision = column_props["NUMERIC_PRECISION"]

        match SQLiteConverter.get_affinity(column_type):
            case SQLiteAffinity.INTEGER:
                return IntType(bits=64)
            case SQLiteAffinity.REAL:
                if precision and precision <= 23:
                    return FloatType(bits=32)
                return FloatType(bits=64)
            case SQLiteAffinity.TEXT:
                return StringType(bytes_=octet_length or SQLITE_MAX_LENGTH)
            case SQLiteAffinity.BLOB:
                return BytesType(bytes_=octet_length or SQLITE_MAX_LENGTH)
            case SQLiteAffinity.NUMERIC:
                # NUMERIC affinity may contain values using all five storage classes
                return UnionType(
                    types=[
                        NullType(),
                        IntType(bits=64),
                        FloatType(bits=64),
                        StringType(bytes_=SQLITE_MAX_LENGTH),
                        BytesType(bytes_=SQLITE_MAX_LENGTH),
                    ]
                )
            case _:
                return UnknownType()

    @staticmethod
    def get_affinity(column_type: str | None) -> SQLiteAffinity:
        """
        Encode affinity rules as defined here:

        https://www.sqlite.org/datatype3.html#determination_of_column_affinity

        :param column_type: The column type to determine the affinity of.
        :return: The affinity of the column type.
        """

        column_type = (column_type or "").upper()

        if not column_type:
            return SQLiteAffinity.BLOB
        elif "INT" in column_type:
            return SQLiteAffinity.INTEGER
        elif "CHAR" in column_type or "TEXT" in column_type or "CLOB" in column_type:
            return SQLiteAffinity.TEXT
        elif "BLOB" in column_type:
            return SQLiteAffinity.BLOB
        elif "REAL" in column_type or "FLOA" in column_type or "DOUB" in column_type:
            return SQLiteAffinity.REAL
        else:
            return SQLiteAffinity.NUMERIC
