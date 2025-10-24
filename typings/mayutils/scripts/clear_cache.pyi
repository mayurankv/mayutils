from _typeshed import Incomplete
from mayutils.data import CACHE_FOLDER as CACHE_FOLDER
from pathlib import Path

app: Incomplete
console: Incomplete

def show_summary(files, dry_run: bool = False) -> None: ...
def clean(
    folder: Path = ...,
    prefix: str | None = ...,
    force: bool = ...,
    verbose: bool = ...,
    dry_run: bool = ...,
) -> None: ...
def clear_cache() -> None: ...
