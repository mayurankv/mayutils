from typing import NamedTuple

class CompressionType(NamedTuple):
    name: str
    file_extension: str
    mime_type: str
    mime_subtypes: list[str]
    is_supported: bool

CompressionTypes = ...
subtype_to_meta: dict[str, CompressionType] = ...

def lookup_by_mime_sub_type(mime_subtype: str) -> CompressionType | None: ...
