import logging
from .abstract import AbstractBrowser
from contextlib import contextmanager
from fsspec import AbstractFileSystem, get_fs_token_paths
from fsspec.implementations.dirfs import DirFileSystem
from pathlib import PurePosixPath
from pydantic import Field
from recap.paths import CatalogPath
from typing import Any, Generator, Union
from urllib.parse import urlparse


log = logging.getLogger(__name__)


class FilesystemRootPath(CatalogPath):
    scheme: str
    name_: str = Field(alias='name')
    template = '/filesystems/{scheme}/instances/{name}'


class DirectoryPath(CatalogPath):
    # Path attr does not contain leading '/'. This is handled in the template.
    path: str
    template = '/{path:path}'


class FilePath(CatalogPath):
    # Path attr does not contain leading '/'. This is handled in the template.
    path: str
    template = '/{path:path}'


FilesystemBrowserPath = Union[
    DirectoryPath,
    FilePath,
]


class FilesystemBrowser(AbstractBrowser):
    """
    A browser that lists filesystem objects. FilesystemBrowser uses fsspec and
    its supported implementations
    (https://filesystem-spec.readthedocs.io/en/latest/api.html#built-in-implementations).

    FilesystemBrowser mirrors the directory structure in the filesystem.
    """

    def __init__(
        self,
        fs: AbstractFileSystem,
        root_: FilesystemRootPath,
    ):
        self.fs = fs
        self.root_ = root_

    def children(self, path: str) -> list[FilesystemBrowserPath] | None:
        paths = []
        if not self.fs.exists(path):
            return None
        if self.fs.isdir(path):
            children = self.fs.ls(path)
            for child in children:
                # Trim duplicate // in the path. [1:] to make path relative.
                child_path = str(PurePosixPath('/', path, child['name']))[1:]
                path_type = DirectoryPath if child['type'] == 'directory' \
                    else FilePath
                paths.append(path_type(path=child_path))
        return paths

    def root(self) -> FilesystemRootPath:
        return self.root_

    @staticmethod
    def default_root(url: str) -> FilesystemRootPath:
        parsed_url = urlparse(url)
        # Given `github://user:pass@main/test-data/test.csv`, return `github`.
        scheme = parsed_url.scheme.split('+')[0]
        # Given `github://user:pass@main/test-data/test.csv`, return `main`.
        name = parsed_url.netloc.split('@')[-1]
        return FilesystemRootPath(
            scheme=scheme or 'file',
            name=name or 'localhost',
        )


@contextmanager
def create_browser(
    url: str,
    name: str | None = None,
    storage_options: dict[str, Any] = {},
    **_,
) -> Generator[FilesystemBrowser, None, None]:
    """
    :param url: The URL to use for the filesystem. If the URL contains a path,
        the FilesystemBrowser will treat all paths relative to the URL path.
    :param name: The name to use in the FilesystemRootPath. If unspecified, the
        URL host is used (or 'localhost' for 'file' schemes).
    :param storage_options: Storage options **kwargs to pass on to the fsspec
        filesystem constructor.
    """

    default_root = FilesystemBrowser.default_root(url)
    fs, _, paths = get_fs_token_paths(url, storage_options=storage_options)

    assert len(paths) == 1, \
        f"Expected to get exactly 1 path from URL, but got paths={paths}"

    fs = DirFileSystem(paths[0], fs)

    yield FilesystemBrowser(
        fs=fs,
        root_=FilesystemRootPath(
            scheme=default_root.scheme,
            name=name or default_root.name_,
        ),
    )