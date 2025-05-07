from pathlib import Path


from mayutils.environment.filesystem import (
    get_module_root,
)

MODULE_ROOT = get_module_root()
CACHE_FOLDER = Path(__file__).parent / "cache"
