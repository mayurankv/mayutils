import os
from pathlib import Path

from mayutils.environment.filesystem import (
    get_root,
    read_file,
)


def get_queries_folders() -> tuple[Path, ...]:
    ROOT = get_root()
    return (
        ROOT / "queries",
        *[
            ROOT / "src" / module / "data" / "queries"
            for module in os.listdir(path=ROOT / "src")
        ],
        Path(__file__).parent / "queries",
    )


QUERIES_FOLDERS = get_queries_folders()


def get_query(
    query_name: Path | str,
    queries_folders: tuple[Path, ...],
) -> str:
    path = Path(query_name)
    for queries_folder in queries_folders:
        try:
            return read_file(path=queries_folder / path)
        except ValueError:
            continue

    return read_file(path=path)


def get_formatted_query(
    query_name: Path | str,
    queries_folders: tuple[Path, ...] = QUERIES_FOLDERS,
    **format_kwargs,
) -> str:
    return get_query(
        query_name=query_name,
        queries_folders=queries_folders,
    ).format(
        **format_kwargs,
    )
