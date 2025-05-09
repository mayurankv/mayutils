from argparse import ArgumentParser
import re
from pathlib import Path

from tomlkit import TOMLDocument


from mayutils.environment.logging import Logger
import tomlkit
from packaging.version import Version
import subprocess

logger = Logger.spawn()


def bump_version_string(
    version: str,
    bump: str,
) -> str:
    v = Version(version=version)
    if bump == "patch":
        return f"{v.major}.{v.minor}.{v.micro + 1}"
    elif bump == "minor":
        return f"{v.major}.{v.minor + 1}.0"
    elif bump == "major":
        return f"{v.major + 1}.0.0"
    else:
        raise ValueError(f"Unknown part to bump: {bump}")


def find_pyproject(
    pyproject_path: Path,
) -> TOMLDocument:
    if not pyproject_path.exists():
        raise FileNotFoundError(
            "pyproject.toml not found, script must ne run in root module folder"
        )

    pyproject = tomlkit.parse(string=pyproject_path.read_text())

    return pyproject


def update_pyproject_version(
    pyproject: TOMLDocument,
    bump: str,
) -> tuple[TOMLDocument, str]:
    project = pyproject["project"]
    current_version = project["version"]  # type: ignore
    project["version"] = f"{  # type: ignore
        bump_version_string(
            version=current_version,  # type: ignore
            bump=bump,
        )
    }"
    pyproject["project"] = project

    return pyproject, project["version"]  # type: ignore


def get_init_file_path(
    pyproject: TOMLDocument,
) -> Path:
    packages = pyproject.get("project", {}).get("packages", {})
    package_info = packages[0] if packages else {}

    name = package_info.get("include", {})
    dir = package_info.get("from", "src")

    init_file_path = Path(dir) / name / "__init__.py"
    if not init_file_path.exists():
        raise FileNotFoundError(f"Could not find __init__.py at {init_file_path}")

    return init_file_path


def update_init_version(
    init_file_path: Path,
    new_version: str,
) -> None:
    updated_init = re.sub(
        pattern=r'__version__\s*=\s*["\']([^"\']+)["\']',
        repl=f'__version__ = "{new_version}"',
        string=init_file_path.read_text(),
    )

    init_file_path.write_text(data=updated_init)


def git_update(
    init_file_path: Path,
    new_version: str,
) -> None:
    subprocess.run(
        args=["git", "add", "pyproject.toml", str(init_file_path)],
        check=True,
    )
    subprocess.run(
        args=["git", "commit", "-m", f"Bump version to {new_version}"],
        check=True,
    )
    subprocess.run(
        args=["git", "tag", f"v{new_version}"],
        check=True,
    )
    subprocess.run(
        args=["git", "push", "--follow-tags"],
        check=True,
    )


def bump() -> None:
    parser = ArgumentParser(description="Bump package version.")
    parser.add_argument(
        "bump",
        nargs="?",
        default="patch",
        choices=["major", "minor", "patch"],
        help="Version part to bump (default: patch)",
    )

    args = parser.parse_args()

    pyproject_path = Path("pyproject.toml")

    pyproject, new_version = update_pyproject_version(
        pyproject=find_pyproject(pyproject_path=pyproject_path),
        bump=args.bump,
    )

    init_file_path = get_init_file_path(pyproject=pyproject)

    update_init_version(
        init_file_path=init_file_path,
        new_version=new_version,
    )

    pyproject_path.write_text(
        data=tomlkit.dumps(data=pyproject),
        encoding="utf-8",
    )

    git_update(
        init_file_path=init_file_path,
        new_version=new_version,
    )

    logger.log(f"Bumped version to {new_version}")


if __name__ == "__main__":
    bump()
