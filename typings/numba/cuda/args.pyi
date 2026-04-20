import abc

"""
Hints to wrap Kernel arguments to indicate how to manage host-device
memory transfers before & after the kernel call.
"""

class ArgHint(metaclass=abc.ABCMeta):
    def __init__(self, value) -> None: ...
    @abc.abstractmethod
    def to_device(self, retr, stream=...):  # -> None:

        ...

class In(ArgHint):
    def to_device(self, retr, stream=...):  # -> DeviceRecord | DeviceNDArray:
        ...

class Out(ArgHint):
    def to_device(self, retr, stream=...):  # -> DeviceRecord | DeviceNDArray:
        ...

class InOut(ArgHint):
    def to_device(self, retr, stream=...):  # -> DeviceRecord | DeviceNDArray:
        ...

def wrap_arg(value, default=...):  # -> ArgHint | InOut:
    ...

__all__ = ["ArgHint", "In", "InOut", "Out", "wrap_arg"]
