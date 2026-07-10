from sqlalchemy import MetaData
from sqlalchemy.orm import DeclarativeBase

SCHEMA = "schema_analytics"


class Base(DeclarativeBase):
    metadata = MetaData(schema=SCHEMA)
