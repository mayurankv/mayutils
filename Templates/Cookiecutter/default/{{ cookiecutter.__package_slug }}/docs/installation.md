# Installation

## Stable Release

To install {{ cookiecutter.project_name }}, run this command in your terminal:

```sh
uv add {{ cookiecutter.__package_slug }}
```

or if you prefer to use `pip`:

```sh
pip install {{ cookiecutter.__package_slug }}
```

## From Source

The source files for {{ cookiecutter.project_name }} can be downloaded from the \[Github repo\](<https://github.com/{{>{> cookiecutter.__gh_slug }}).

You can either clone the public repository:

```sh
git clone git://github.com/{{ cookiecutter.github_username }}/{{ cookiecutter.__package_slug }}
```

Or download the \[tarball\](<https://github.com/{{>{> cookiecutter.__gh_slug }}/tarball/master):

```sh
curl -OJL https://github.com/{{ cookiecutter.__gh_slug }}/tarball/master
```

Once you have a copy of the source, you can install it with:

```sh
cd {{ cookiecutter.__package_slug }}
uv pip install .
```
