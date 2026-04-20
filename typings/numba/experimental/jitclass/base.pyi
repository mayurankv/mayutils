from numba.core import types
from numba.core.datamodel import models
from numba.core.serialize import disable_pickling
from numba.core.typing import templates

class InstanceModel(models.StructModel):
    def __init__(self, dmm, fe_typ) -> None: ...

class InstanceDataModel(models.StructModel):
    def __init__(self, dmm, fe_typ) -> None: ...

_ctor_template = ...

@disable_pickling
class JitClassType(type):
    def __new__(cls, name, bases, dct):  # -> Self:
        ...
    def __instancecheck__(cls, instance) -> bool:  # -> bool:
        ...
    def __call__(
        cls, *args, **kwargs
    ):  # -> Any | Callable[..., FakeCUDAKernel] | Callable[..., CUDADispatcher] | FakeCUDAKernel | CUDADispatcher | FunctionType | None:
        ...

def register_class_type(cls, spec, class_ctor, builder):  # -> type[__class_JitClassType]:

    ...

class ConstructorTemplate(templates.AbstractTemplate):
    def generic(self, args, kws):  # -> Signature:
        ...

class ClassBuilder:
    class_impl_registry = ...
    implemented_methods = ...
    def __init__(self, class_type, typingctx, targetctx) -> None: ...
    def register(self):  # -> None:

        ...

@templates.infer_getattr
class ClassAttribute(templates.AttributeTemplate):
    key = types.ClassInstanceType
    def generic_resolve(self, instance, attr):  # -> BoundFunction | None:
        ...

@ClassBuilder.class_impl_registry.lower_getattr_generic(types.ClassInstanceType)
def get_attr_impl(context, builder, typ, value, attr):  # -> Any:

    ...
@ClassBuilder.class_impl_registry.lower_setattr_generic(types.ClassInstanceType)
def set_attr_impl(context, builder, sig, args, attr):  # -> None:

    ...
def imp_dtor(context, module, instance_type):  # -> Function:
    ...
@ClassBuilder.class_impl_registry.lower(types.ClassType, types.VarArg(types.Any))
def ctor_impl(context, builder, sig, args): ...
