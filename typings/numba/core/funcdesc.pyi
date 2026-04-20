def default_mangler(name, argtypes, *, abi_tags=..., uid=...):  # -> str:
    ...
def qualifying_prefix(modname, qualname):  # -> str:

    ...

class FunctionDescriptor:
    __slots__ = ...
    def __init__(
        self,
        native,
        modname,
        qualname,
        unique_name,
        doc,
        typemap,
        restype,
        calltypes,
        args,
        kws,
        mangler=...,
        argtypes=...,
        inline=...,
        noalias=...,
        env_name=...,
        global_dict=...,
        abi_tags=...,
        uid=...,
    ) -> None: ...
    def lookup_globals(self):  # -> dict[str, Any]:

        ...
    def lookup_module(self):  # -> ModuleType:

        ...
    def lookup_function(self):  # -> Any:

        ...
    @property
    def llvm_func_name(self):  # -> str:

        ...
    @property
    def llvm_cpython_wrapper_name(self):  # -> str:

        ...
    @property
    def llvm_cfunc_wrapper_name(self):  # -> str:

        ...

class PythonFunctionDescriptor(FunctionDescriptor):
    __slots__ = ...
    @classmethod
    def from_specialized_function(cls, func_ir, typemap, restype, calltypes, mangler, inline, noalias, abi_tags):  # -> Self:

        ...
    @classmethod
    def from_object_mode_function(cls, func_ir):  # -> Self:

        ...

class ExternalFunctionDescriptor(FunctionDescriptor):
    __slots__ = ...
    def __init__(self, name, restype, argtypes) -> None: ...
