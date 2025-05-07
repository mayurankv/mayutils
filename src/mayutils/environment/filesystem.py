import os
import inspect
from git import Repo, InvalidGitRepositoryError
from pathlib import Path
import urllib.parse


def get_root() -> Path:
    try:
        return Path(
            Repo(
                path=".",
                search_parent_directories=True,
            ).working_dir
        )
    except InvalidGitRepositoryError:
        return Path(os.getcwd())


def get_module_root() -> Path:
    defining_module = inspect.getmodule(inspect.currentframe())
    return (
        Path(defining_module.__file__).parent
        if defining_module is not None and defining_module.__file__ is not None
        else get_root()
    )


def read_file(
    path: Path | str,
) -> str:
    filepath = Path(path)
    if filepath.is_file():
        with open(
            file=filepath,
            mode="r",
        ) as file:
            return file.read()

    raise ValueError(f"File {path} could not be found")


def encode_path(
    path: Path | str,
) -> str:
    return urllib.parse.quote(string=str(path).replace("/", "#"))


def decode_path(
    encoded_path: str,
) -> Path:
    return Path(urllib.parse.unquote(string=encoded_path).replace("#", "/"))
