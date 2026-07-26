# Security policy

## Supported versions

Kettle is pre-1.0. Security fixes are applied to the latest release and the
current `main` branch.

## Reporting a vulnerability

Please do not open a public issue for a suspected vulnerability. Use GitHub's
private vulnerability reporting for
[charlesberret/kettle-core](https://github.com/charlesberret/kettle-core/security/advisories/new).
If that surface is unavailable, contact the maintainer through the address in
the Git commit metadata.

Include:

- the affected version or commit;
- the smallest reproducible case;
- the expected and observed security boundary;
- any evidence of data access, command execution, or network exposure.

You should receive an acknowledgement within seven days. A fix and disclosure
timeline will be coordinated after the report is reproduced.

## Security boundaries

Kettle is a single-user, local-first application. Its server is intended to bind
only to `127.0.0.1`; file operations must remain fenced to registered roots; and
provider credentials remain with the provider CLI. Remote or multi-user
deployment is not currently supported.
