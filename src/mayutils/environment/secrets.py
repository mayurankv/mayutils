from pathlib import Path
from typing import Optional
from dotenv import load_dotenv, find_dotenv


def load_secrets(
    env_file: Optional[Path | str] = None,
) -> bool:
    if env_file is None:
        env_file = find_dotenv()

    return load_dotenv(dotenv_path=env_file)
