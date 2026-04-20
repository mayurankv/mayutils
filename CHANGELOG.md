# Changelog

All notable changes to `mayutils` will be documented here.

This project follows [Semantic Versioning](https://semver.org/) and the [Keep a Changelog](https://keepachangelog.com/) conventions. Releases are produced by [commitizen](https://commitizen-tools.github.io/commitizen/) from [Conventional Commits](https://www.conventionalcommits.org/) — `feat` bumps the minor version, `fix` bumps the patch, and a `!` or `BREAKING CHANGE:` footer bumps the major.

## v1.2.52

### Added

- Initial commitizen-managed changelog.
- Optional-dependency groups (`plotting`, `notebook`, `google`, `microsoft`, `snowflake`, `streamlit`, `stats`, `dataframes`, `datetime`, `pdf`, `web`, `cli`, `async`, `filesystem`, `keyring`, `types`, `all`).
- `docs` and `testing` dependency groups for mkdocs-material site and pytest.
- mkdocs-material documentation site with auto-generated API reference.
- CI workflows (`ci.yaml`, `docs.yaml`, `merge-gatekeeper.yaml`) and renovate config.
- Contributing guide, security policy, roadmap (translated from `.todo`).
