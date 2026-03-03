# Security Policy

## Scope
This repository is an MCP bridge. It does not store notes directly and should not contain database credentials.

## Supported versions
Only the latest main branch is supported for security fixes.

## Reporting a vulnerability
Please open a private security advisory on GitHub (preferred) or contact the maintainer directly.
Do not post sensitive exploit details in public issues.

## Hardening guidance
- Keep the memory gateway private to your network unless you add authentication and TLS.
- Configure an API key and pass it via `SECOND_BRAIN_API_KEY`.
- Never store secrets in notes; treat memory content as potentially retrievable by connected agents.
