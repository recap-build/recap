import logging
import sqlalchemy as sa
from contextlib import contextmanager
from recap.analyzers.abstract import AbstractAnalyzer
from typing import Generator


log = logging.getLogger(__name__)


class AbstractDatabaseAnalyzer(AbstractAnalyzer):
    def __init__(
        self,
        engine: sa.engine.Engine,
    ):
        self.engine = engine

    def _table_or_view(self, table: str | None, view: str | None) -> str:
        table_or_view = table or view
        assert table_or_view, 'Either table or view must be set.'
        return table_or_view

    @classmethod
    @contextmanager
    def open(cls, **config) -> Generator['AbstractDatabaseAnalyzer', None, None]:
        assert 'url' in config, \
            f"Config for {cls.__name__} is missing `url` config."
        engine = sa.create_engine(config['url'])
        yield cls(engine)
