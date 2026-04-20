_msg_deprecated_signature_arg = ...

def jit(
    func_or_sig=..., device=..., inline=..., link=..., debug=..., opt=..., lineinfo=..., cache=..., **kws
):  # -> Callable[..., FakeCUDAKernel] | Callable[..., CUDADispatcher] | FakeCUDAKernel | CUDADispatcher:

    ...
def declare_device(name, sig):  # -> ExternFunction:

    ...
