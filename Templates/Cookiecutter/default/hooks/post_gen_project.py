import os


for dir in [".secrets"]:
    os.mkdir(path=dir)

for paths in [".env", ".streamlit/secrets.toml"]:
    with open(
        file=paths,
        mode="a",
    ) as env_file:
        pass
