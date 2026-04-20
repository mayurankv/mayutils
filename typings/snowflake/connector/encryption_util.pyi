from typing import IO, TYPE_CHECKING

from .constants import EncryptionMetadata, MaterialDescriptor
from .storage_client import SnowflakeFileEncryptionMaterial

block_size = ...
if TYPE_CHECKING: ...
logger = ...

def matdesc_to_unicode(matdesc: MaterialDescriptor) -> str: ...

class SnowflakeEncryptionUtil:
    @staticmethod
    def get_secure_random(byte_length: int) -> bytes: ...
    @staticmethod
    def encrypt_stream(
        encryption_material: SnowflakeFileEncryptionMaterial, src: IO[bytes], out: IO[bytes], chunk_size: int = ...
    ) -> EncryptionMetadata: ...
    @staticmethod
    def encrypt_file(
        encryption_material: SnowflakeFileEncryptionMaterial, in_filename: str, chunk_size: int = ..., tmp_dir: str | None = ...
    ) -> tuple[EncryptionMetadata, str]: ...
    @staticmethod
    def decrypt_stream(
        metadata: EncryptionMetadata,
        encryption_material: SnowflakeFileEncryptionMaterial,
        src: IO[bytes],
        out: IO[bytes],
        chunk_size: int = ...,
    ) -> None: ...
    @staticmethod
    def decrypt_file(
        metadata: EncryptionMetadata,
        encryption_material: SnowflakeFileEncryptionMaterial,
        in_filename: str,
        chunk_size: int = ...,
        tmp_dir: str | None = ...,
        unsafe_file_write: bool = ...,
    ) -> str: ...
