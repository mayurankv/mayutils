def null(
    *args,
    **kwargs,
) -> None:
    return None


def set_inline(
    object,
    property,
    value,
) -> None:
    object.__setitem__(property, value)

    return object
