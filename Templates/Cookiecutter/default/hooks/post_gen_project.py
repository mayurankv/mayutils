from pathlib import Path


for directory in [".secrets"]:
    Path(directory).mkdir(exist_ok=True)

for path in [".env", ".streamlit/secrets.toml"]:
    Path(path).touch()

for template_file in Path(".").rglob("*.template"):
    template_file.rename(template_file.with_suffix(""))
