from abc import ABC, abstractmethod

class Browser(ABC):
    def __init__(self, flags, disable_logging) -> None: ...
    @property
    @abstractmethod
    def executable(self):  # -> None:
        ...
    @executable.setter
    @abstractmethod
    def executable(self, value):  # -> None:
        ...
    @abstractmethod
    def screenshot(self, *args, **kwargs):  # -> None:
        ...
    @abstractmethod
    def __enter__(self):  # -> None:
        ...
    @abstractmethod
    def __exit__(self, *exc):  # -> None:
        ...
    @property
    @abstractmethod
    def disable_logging(self):  # -> None:
        ...

class CDPBrowser(Browser):
    def __init__(self, flags, cdp_port, disable_logging) -> None: ...
