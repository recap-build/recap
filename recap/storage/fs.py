import fsspec
import json
from .abstract import AbstractStorage
from contextlib import contextmanager
from os.path import join
from typing import Any, List, Generator
from urllib.parse import urlparse


class FilesystemStorage(AbstractStorage):
    def __init__(
        self,
        root: str,
        fs: fsspec.AbstractFileSystem,
    ):
        self.root = root
        self.fs = fs

    def put_instance(self, infra: str, instance: str):
        dirname = join(
            self.root,
            'databases',infra,
            'instances', instance,
        )
        self.fs.mkdirs(dirname, exist_ok=True)

    def put_schema(self, infra: str, instance: str, schema: str):
        dirname = join(
            self.root,
            'databases', infra,
            'instances', instance,
            'schemas', schema,
        )
        self.fs.mkdirs(dirname, exist_ok=True)

    def put_table(self, infra: str, instance: str, schema: str, table: str):
        dirname = join(
            self.root,
            'databases', infra,
            'instances', instance,
            'schemas', schema,
            'tables', table,
        )
        self.fs.mkdirs(dirname, exist_ok=True)

    def put_view(self, infra: str, instance: str, schema: str, view: str):
        dirname = join(
            self.root,
            'databases', infra,
            'instances', instance,
            'schemas', schema,
            'views', view,
        )
        self.fs.mkdirs(dirname, exist_ok=True)

    def put_metadata(
        self,
        infra: str,
        instance: str,
        type: str,
        metadata: dict[str, Any],
        schema: str | None = None,
        table: str | None = None,
        view: str | None = None,
    ):
        # TODO this code is dupe'd all over
        dirname = join(
            self.root,
            'databases', infra,
            'instances', instance,
        )
        if schema:
            dirname = join(dirname, 'schemas', schema)
        if table:
            assert schema is not None, "Schema must be set if putting table metadata"
            dirname = join(dirname, 'tables', table)
        elif view:
            assert schema is not None, "Schema must be set if putting view metadata"
            dirname = join(dirname, 'views', view)
        dirname = join(dirname, 'metadata')
        filename = join(dirname, f"{type}.json")
        if not self.fs.exists(dirname):
            self.fs.mkdirs(dirname, exist_ok=True)
        with self.fs.open(filename, 'w') as f:
            json.dump(metadata, f) # pyright: ignore [reportGeneralTypeIssues]

    def remove_instance(self, infra: str, instance: str):
        dirname = join(
            self.root,
            'databases', infra,
            'instances', instance,
        )
        try:
            self.fs.rm(dirname, recursive=True)
        except FileNotFoundError:
            # File is already deleted
            # TODO Maybe we should raise a StorageException here?
            pass

    def remove_schema(self, infra: str, instance: str, schema: str):
        dirname = join(
            self.root,
            'databases', infra,
            'instances', instance,
            'schemas', schema,
        )
        try:
            self.fs.rm(dirname, recursive=True)
        except FileNotFoundError:
            # File is already deleted
            # TODO Maybe we should raise a StorageException here?
            pass

    def remove_table(self, infra: str, instance: str, schema: str, table: str):
        dirname = join(
            self.root,
            'databases', infra,
            'instances', instance,
            'schemas', schema,
            'tables', table,
        )
        try:
            self.fs.rm(dirname, recursive=True)
        except FileNotFoundError:
            # File is already deleted
            # TODO Maybe we should raise a StorageException here?
            pass

    def remove_view(self, infra: str, instance: str, schema: str, view: str):
        dirname = join(
            self.root,
            'databases', infra,
            'instances', instance,
            'schemas', schema,
            'views', view,
        )
        try:
            self.fs.rm(dirname, recursive=True)
        except FileNotFoundError:
            # File is already deleted
            # TODO Maybe we should raise a StorageException here?
            pass

    def remove_metadata(
        self,
        infra: str,
        instance: str,
        type: str,
        schema: str | None = None,
        table: str | None = None,
        view: str | None = None,
    ):
        # TODO this code is dupe'd all over
        dirname = join(
            self.root,
            'databases', infra,
            'instances', instance,
        )
        if schema:
            dirname = join(dirname, 'schemas', schema)
        if table:
            assert schema is not None, "Schema must be set if putting table metadata"
            dirname = join(dirname, 'tables', table)
        elif view:
            assert schema is not None, "Schema must be set if putting view metadata"
            dirname = join(dirname, 'views', view)
        dirname = join(dirname, 'metadata')
        filename = join(dirname, f"{type}.json")
        try:
            self.fs.rm(filename)
        except FileNotFoundError:
            # File is already deleted
            # TODO Maybe we should raise a StorageException here?
            pass

    def list_schemas(self, infra: str, instance: str) -> List[str]:
        dirname = join(
            self.root,
            'databases', infra,
            'instances', instance,
        )
        schemas = self.fs.ls(dirname, detail=False) if self.fs.exists(dirname) else []
        return list(filter(lambda p: p == 'metadata', schemas))

    def list_tables(self, infra: str, instance: str, schema: str) -> List[str]:
        dirname = join(
            self.root,
            'databases', infra,
            'instances', instance,
            'schemas', schema,
            'tables',
        )
        tables = self.fs.ls(dirname, detail=False) if self.fs.exists(dirname) else []
        return list(filter(lambda p: p == 'metadata', tables))

    def list_views(self, infra: str, instance: str, schema: str) -> List[str]:
        dirname = join(
            self.root,
            'databases', infra,
            'instances', instance,
            'schemas', schema,
            'views',
        )
        views = self.fs.ls(dirname, detail=False) if self.fs.exists(dirname) else []
        return list(filter(lambda p: p == 'metadata', views))

    def list_metadata(
        self,
        infra: str,
        instance: str,
        schema: str | None = None,
        table: str | None = None,
        view: str | None = None,
    ) -> List[str] | None:
        # TODO implement list_metadata
        raise NotImplementedError

    def get_metadata(
        self,
        infra: str,
        instance: str,
        type: str,
        schema: str | None = None,
        table: str | None = None,
        view: str | None = None,
    ) -> dict[str, str] | None:
        # TODO implement get_metadata
        raise NotImplementedError


@contextmanager
def open(**config) -> Generator[FilesystemStorage, None, None]:
        url = urlparse(config['url'])
        storage_options = config.get('options', {})
        yield FilesystemStorage(
            url.path,
            fsspec.filesystem(url.scheme, **storage_options, auto_mkdir=True),
        )
