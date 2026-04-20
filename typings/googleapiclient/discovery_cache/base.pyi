import abc

"""An abstract class for caching the discovery document."""

class Cache:
    __metaclass__ = abc.ABCMeta
    @abc.abstractmethod
    def get(self, url): ...
    @abc.abstractmethod
    def set(self, url, content): ...
