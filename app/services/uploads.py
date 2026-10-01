from dataclasses import dataclass
import hashlib
from pathlib import Path
from uuid import uuid4
from starlette.concurrency import run_in_threadpool

from app.face.images import MAX_BYTES, decode_image
from app.face.types import FaceError


@dataclass(frozen=True)
class StoredUpload:
    path: str
    digest: str


async def receive_photo(upload, storage_root: Path) -> StoredUpload:
    data = bytearray()
    try:
        while chunk := await upload.read(64 * 1024):
            data.extend(chunk)
            if len(data) > MAX_BYTES:
                raise FaceError('IMAGE_TOO_LARGE')
    finally:
        await upload.close()
    await run_in_threadpool(decode_image, bytes(data))
    return await run_in_threadpool(store_bytes, bytes(data), storage_root)


def store_bytes(data: bytes, storage_root: Path) -> StoredUpload:
    """Disk writes and hashing must not block the upload event loop."""
    root = storage_root / 'uploads'
    root.mkdir(parents=True, exist_ok=True)
    name = uuid4().hex + '.image'
    target = root / name
    try:
        with target.open('xb') as output:
            output.write(data)
    except Exception:
        target.unlink(missing_ok=True)
        raise
    return StoredUpload('uploads/' + name, hashlib.sha256(data).hexdigest())


def stored_path(root: Path, relative: str) -> Path:
    candidate = (root / relative).resolve()
    if not candidate.is_relative_to(root.resolve()) or candidate == root.resolve():
        raise ValueError('Invalid storage path')
    return candidate
