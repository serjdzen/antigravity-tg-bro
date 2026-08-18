# Security Policy

## 2-Tier Defense Architecture

Antigravity Telegram Bot is designed with a defense-in-depth model to protect local developer machines:

1. **Native Deny-List (`settings.json`)**:
   - Destructive commands (`rm`, `rmdir`, `unlink`, `git reset --hard`, `git clean -f`, `dd`, `shutdown`, `reboot`) are blocked at the engine layer by default.
2. **Deterministic Context Override**:
   - High-privilege turns run inside an asynchronous context manager that temporarily relaxes rules only for the requested action and guarantees restoration in `finally:`.
3. **Single-User Lock**:
   - Concurrency locks prevent overlapping turn execution and race conditions.
4. **Environment Isolation**:
   - Bot configuration is isolated from child MCP processes to prevent Pydantic settings schema collisions.

## Reporting Security Vulnerabilities

If you discover a security vulnerability or potential token leak vector:
- Please **do not** report security vulnerabilities via public GitHub issues.
- Send an advisory directly through GitHub Security Advisories on this repository or contact the maintainer directly.
