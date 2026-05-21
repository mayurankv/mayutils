import os
from pathlib import Path


for dir in [".secrets"]:
    os.mkdir(path=dir)

for paths in [".env", ".streamlit/secrets.toml"]:
    with open(
        file=paths,
        mode="a",
    ) as env_file:
        pass

for template_file in Path(".").rglob("*.template"):
    template_file.rename(template_file.with_suffix(""))
