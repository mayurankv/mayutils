import pathlib
from functools import cached_property
from typing import Protocol

class PlatformDirsProto(Protocol):
    @property
    def user_config_path(self) -> pathlib.Path: ...

class SFPlatformDirs:
    def __init__(self, single_dir: str, **kwargs) -> None: ...
    @cached_property
    def user_config_path(self) -> str: ...
