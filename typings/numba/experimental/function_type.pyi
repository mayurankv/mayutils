from numba.core import types
from numba.core.ccallback import CFunc
from numba.core.imputils import lower_cast, lower_constant
from numba.core.types import FunctionPrototype, FunctionType, UndefinedFunctionType, WrapperAddressProtocol
from numba.extending import box, models, register_model, typeof_impl, unbox

"""Provides Numba type, FunctionType, that makes functions as
instances of a first-class function type.
"""

@typeof_impl.register(WrapperAddressProtocol)
@typeof_impl.register(CFunc)
def typeof_function_type(val, c):  # -> FunctionType:
    ...

@register_model(FunctionPrototype)
class FunctionProtoModel(models.PrimitiveModel):
    def __init__(self, dmm, fe_type) -> None: ...

@register_model(FunctionType)
@register_model(UndefinedFunctionType)
class FunctionModel(models.StructModel):
    def __init__(self, dmm, fe_type) -> None: ...

@lower_constant(types.Dispatcher)
def lower_constant_dispatcher(context, builder, typ, pyval): ...
@lower_constant(FunctionType)
def lower_constant_function_type(context, builder, typ, pyval):  # -> Any:
    ...

lower_get_wrapper_address = ...
lower_get_jit_address = ...

@unbox(FunctionType)
def unbox_function_type(typ, obj, c): ...
@box(FunctionType)
def box_function_type(typ, val, c): ...
@lower_cast(UndefinedFunctionType, FunctionType)
def lower_cast_function_type_to_function_type(context, builder, fromty, toty, val): ...
@lower_cast(types.Dispatcher, FunctionType)
def lower_cast_dispatcher_to_function_type(context, builder, fromty, toty, val):  # -> Any:
    ...
