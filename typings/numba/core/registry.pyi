from numba.core import cpu, dispatcher, utils
from numba.core.descriptors import TargetDescriptor

class CPUTarget(TargetDescriptor):
    options = cpu.CPUTargetOptions
    @property
    def target_context(self):  # -> threadsafe_cached_property:

        ...
    @property
    def typing_context(self):  # -> threadsafe_cached_property:

        ...

cpu_target = ...

class CPUDispatcher(dispatcher.Dispatcher):
    targetdescr = ...

class DelayedRegistry(utils.UniqueDict):
    def __init__(self, *args, **kws) -> None: ...
    def __getitem__(self, item): ...
    def __setitem__(self, key, value) -> None:  # -> None:
        ...
