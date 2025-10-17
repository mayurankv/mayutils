from typing import Optional
from re import sub


def noneish_string(
    string: Optional[str],
) -> Optional[str]:
    return None if string == "" else string


def snakify(
    string: str,
) -> str:
    return "_".join(
        sub(
            pattern="([A-Z][a-z]+)",
            repl=r" \1",
            string=sub(
                pattern="([A-Z]+)",
                repl=r" \1",
                string=string.replace("-", " "),
            ),
        ).split()
    ).lower()


def unsnakify(
    string: str,
) -> str:
    return string.replace("_", " ").title()


def kebabify(
    string: str,
) -> str:
    return "-".join(
        sub(
            pattern=r"(\s|_|-)+",
            repl=" ",
            string=sub(
                pattern=r"[A-Z]{2,}(?=[A-Z][a-z]+[0-9]*|\b)|[A-Z]?[a-z]+[0-9]*|[A-Z]|[0-9]+",
                repl=r" \1",
                string=string,
            ).lower(),
        ).split()
    )


def camel(
    string: str,
) -> str:
    string = (
        sub(
            pattern=r"(_|-)+",
            repl=" ",
            string=string,
        )
        .title()
        .replace(" ", "")
    )
    return "".join([string[0].lower(), string[1:]])
