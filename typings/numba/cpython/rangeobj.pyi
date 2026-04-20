import operator

from numba.core import types
from numba.core.extending import overload, register_jitable
from numba.core.imputils import lower_cast

"""
Implementation of the range object for fixed-size integers.
"""

def make_range_iterator(typ):  # -> Any:

    ...
def make_range_impl(int_type, range_state_type, range_iter_type) -> None:  # -> None:
    ...

range_impl_map = ...

@lower_cast(types.RangeType, types.RangeType)
def range_to_range(context, builder, fromty, toty, val):  # -> Constant:
    ...
def make_range_attr(index, attribute):  # -> None:
    ...
@register_jitable
def impl_contains_helper(robj, val):  # -> Literal[False]:
    ...
@overload(operator.contains)
def impl_contains(robj, val):  # -> Callable[..., Any | Literal[False]] | Callable[..., Literal[False]] | None:
    ...
