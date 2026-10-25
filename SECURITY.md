# Security Policy

## Supported Versions

Security fixes target the current development line. Older versions may not receive updates.

| Version | Supported |
| --- | --- |
| `dev` | Yes |
| `3.0.x` | Best effort |
| Older versions | No |

## Reporting a Vulnerability

Please do not report exploitable vulnerabilities in public issues.

Use [GitHub's private vulnerability reporting](https://github.com/TheJeager/Carlotta-Music/security/advisories/new) to share a report with the maintainers. Include the affected commit or version, steps to reproduce, and potential impact. Do not include live bot tokens, Telegram session strings, MongoDB credentials, or cookie contents.

The maintainers should acknowledge a report when they can review it and will coordinate any fix or disclosure through the private report. If private vulnerability reporting is unavailable, contact a repository maintainer privately rather than posting exploit details publicly.

## Security-sensitive features

- `/eval` and `/exec` execute arbitrary Python code and must remain owner-only.
- Broadcast and sudo commands should be limited to trusted accounts.
- Keep `.env`, session files, downloaded cookies, and runtime logs out of commits.
