from numba.core.extending import register_jitable

@register_jitable
def gen_mask(max): ...
@register_jitable
def buffered_bounded_bool(bitgen, off, rng, bcnt, buf):  # -> tuple[Any, Any, Any] | tuple[Any, Any | Literal[31], Any]:
    ...
@register_jitable
def buffered_uint8(bitgen, bcnt, buf):  # -> tuple[Any | Signature, Any | Literal[3], Any]:
    ...
@register_jitable
def buffered_uint16(bitgen, bcnt, buf):  # -> tuple[Any | Signature, Any | Literal[1], Any]:
    ...
@register_jitable
def buffered_bounded_lemire_uint8(bitgen, rng, bcnt, buf):  # -> tuple[Any, Any | Literal[3], Any]:

    ...
@register_jitable
def buffered_bounded_lemire_uint16(bitgen, rng, bcnt, buf):  # -> tuple[Any, Any | Literal[1], Any]:

    ...
@register_jitable
def buffered_bounded_lemire_uint32(bitgen, rng): ...
@register_jitable
def bounded_lemire_uint64(bitgen, rng): ...
@register_jitable
def random_bounded_uint64_fill(bitgen, low, rng, size, dtype):  # -> _Array1D[float64]:

    ...
@register_jitable
def random_bounded_uint32_fill(bitgen, low, rng, size, dtype):  # -> _Array1D[float64]:

    ...
@register_jitable
def random_bounded_uint16_fill(bitgen, low, rng, size, dtype):  # -> _Array1D[float64]:

    ...
@register_jitable
def random_bounded_uint8_fill(bitgen, low, rng, size, dtype):  # -> _Array1D[float64]:

    ...
@register_jitable
def random_bounded_bool_fill(bitgen, low, rng, size, dtype):  # -> _Array1D[float64]:

    ...
@register_jitable
def random_interval(bitgen, max_val):  # -> Signature | Literal[0]:
    ...
