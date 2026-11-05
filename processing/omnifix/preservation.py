import hashlib
from pathlib import Path


def checksum(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def verify_original(path: Path, expected: str):
    if checksum(path) != expected:
        raise ValueError("Original source integrity verification failed")
