# Security Policy

## Reporting a Vulnerability

If you discover a security vulnerability in `mayutils`, please report it responsibly.

**Do not open a public GitHub issue.**

Instead, email Mayuran Visakan at `mayuran.k.v@gmail.com` with:

- A description of the vulnerability
- Steps to reproduce
- Potential impact

We will acknowledge receipt as soon as possible and aim to provide a fix or mitigation plan quickly.

## Supported Versions

Only the latest release is actively supported with security updates.

## Scope

`mayutils` is a utility library. It does not host services, handle authentication directly, or persist data on the user's behalf. Security-relevant surfaces:

- Secret loading (`mayutils.environment.secrets`, `mayutils.environment.oauth`)
- Webdriver factories (`mayutils.environment.webdrivers`)
- Database engine factories (`mayutils.environment.databases`)
- File/HTML export paths
- Dependency vulnerabilities in the optional extras
