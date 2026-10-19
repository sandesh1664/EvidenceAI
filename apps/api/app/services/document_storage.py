"""Private, flat, descriptor-relative local storage; keys never contain client paths."""
from contextlib import contextmanager
from dataclasses import dataclass
import hashlib
import os
from pathlib import Path
import re
import stat
from typing import BinaryIO, Protocol
import uuid


class StorageError(Exception):
    pass


class UploadTooLarge(Exception):
    pass


@dataclass(frozen=True)
class StoredUpload:
    key: str
    size: int
    checksum: str


class DocumentStorage(Protocol):
    def stage(self, key: str, stream: BinaryIO, limit: int) -> StoredUpload: ...
    def open(self, key: str, *, staged: bool = False) -> BinaryIO: ...
    def promote(self, key: str) -> None: ...
    def delete(self, key: str) -> None: ...


class LocalDocumentStorage:
    def __init__(self, root: Path):
        self.root = Path(root)
        if not self.root.is_absolute() or self.root == Path('/'):
            raise StorageError("Invalid private storage root")
        try:
            with self._directory(create=True) as fd:
                os.fchmod(fd, 0o700)
        except OSError:
            raise StorageError("Private storage unavailable") from None

    @staticmethod
    def new_key():
        return uuid.uuid4().hex

    @staticmethod
    def validate_key(key):
        if not re.fullmatch(r"[a-f0-9]{32}", key):
            raise StorageError("Invalid storage key")

    @contextmanager
    def _directory(self, *, create=False):
        fd = os.open('/', os.O_RDONLY | os.O_DIRECTORY)
        try:
            for component in self.root.parts[1:]:
                if component in {'.', '..'}:
                    raise StorageError("Invalid storage root")
                if create:
                    try:
                        os.mkdir(component, mode=0o700, dir_fd=fd)
                    except FileExistsError:
                        pass
                child = os.open(component, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
                os.close(fd)
                fd = child
            yield fd
        finally:
            os.close(fd)

    def stage(self, key, stream, limit):
        self.validate_key(key)
        size, checksum = 0, hashlib.sha256()
        try:
            with self._directory() as directory:
                fd = os.open(key+'.part', os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600, dir_fd=directory)
                try:
                    with os.fdopen(fd, 'wb') as target:
                        while data := stream.read(min(65536, limit-size+1)):
                            size += len(data)
                            if size > limit:
                                raise UploadTooLarge()
                            checksum.update(data)
                            target.write(data)
                        target.flush()
                        os.fsync(target.fileno())
                except BaseException:
                    os.unlink(key+'.part', dir_fd=directory)
                    raise
            return StoredUpload(key, size, checksum.hexdigest())
        except OSError:
            raise StorageError("Private storage unavailable") from None

    def open(self, key, *, staged=False):
        self.validate_key(key)
        try:
            with self._directory() as directory:
                fd = os.open(key+('.part' if staged else ''), os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=directory)
            info = os.fstat(fd)
            if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
                os.close(fd)
                raise StorageError("Invalid stored object")
            return os.fdopen(fd, 'rb')
        except OSError:
            raise StorageError("Original unavailable") from None

    def promote(self, key):
        self.validate_key(key)
        try:
            with self._directory() as directory:
                # Atomic publication without overwriting a pre-existing object.
                os.link(key+'.part', key, src_dir_fd=directory, dst_dir_fd=directory, follow_symlinks=False)
                os.unlink(key+'.part', dir_fd=directory)
                os.fsync(directory)
        except OSError:
            raise StorageError("Private storage unavailable") from None

    def delete(self, key):
        self.validate_key(key)
        try:
            with self._directory() as directory:
                for name in [key, key+'.part']:
                    try:
                        os.unlink(name, dir_fd=directory)
                    except FileNotFoundError:
                        pass
                os.fsync(directory)
        except OSError:
            raise StorageError("Private storage cleanup unavailable") from None


def get_document_storage():
    from app.core.config import get_settings
    try:
        return LocalDocumentStorage(get_settings().document_storage_root)
    except StorageError:
        from fastapi import HTTPException
        raise HTTPException(503, 'Document storage unavailable') from None
