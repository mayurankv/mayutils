from typing import Optional


def noneish_string(
    string: Optional[str],
) -> Optional[str]:
    return None if string == "" else string
