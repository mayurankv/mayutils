# Installation

## Stable Release

To install {{ cookiecutter.project_name }}, run this command in your terminal:

```sh
uv add {{ cookiecutter.package_name }}
```

or if you prefer to use `pip`:

```sh
pip install {{ cookiecutter.package_name }}
```

## From Source

The source files for {{ cookiecutter.project_name }} can be downloaded from the \[Github repo\](https://github.com/{{ cookiecutter.\_\_gh_slug }}).

You can either clone the public repository:

```sh
git clone git://github.com/{{ cookiecutter.github_username }}/{{ cookiecutter.project_slug }}
```

Or download the \[tarball\](https://github.com/{{ cookiecutter.\_\_gh_slug }}/tarball/master):

```sh
curl -OJL https://github.com/{{ cookiecutter.__gh_slug }}/tarball/master
```

Once you have a copy of the source, you can install it with:

```sh
cd {{ cookiecutter.project_slug }}
uv pip install .
```
