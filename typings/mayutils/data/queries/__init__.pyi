from _typeshed import Incomplete
from mayutils.environment.filesystem import get_root as get_root, read_file as read_file
from pathlib import Path

def get_queries_folders() -> tuple[Path, ...]: ...

QUERIES_FOLDERS: Incomplete

def get_query(
    query_name: Path | str, queries_folders: tuple[Path, ...] = ...
) -> str: ...
def get_formatted_query(
    query_name: Path | str, queries_folders: tuple[Path, ...] = ..., **format_kwargs
) -> str: ...
