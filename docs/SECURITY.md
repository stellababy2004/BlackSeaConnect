# BlackSeaConnect Security Overview

This document summarizes the current security posture, operational expectations, and known limitations of BlackSeaConnect.

It is intended as a living document and should be reviewed whenever authentication, deployment, infrastructure, payments, analytics, or data handling changes.

## 1. Secrets and configuration

Production secrets must be provided through environment variables or the deployment platform secret store.

Never commit:

- `SECRET_KEY`
- `ADMIN_PASSWORD`
- `ADMIN_SUPER_PASSWORD`
- SMTP credentials
- Stripe secret keys
- webhook secrets
- API tokens
- database credentials or private connection strings

`SECRET_KEY` must be non-default and at least 32 characters in protected environments.

The application validates critical production configuration before deployment.

## 2. Admin authentication

Admin access uses HTTP Basic Authentication with credentials supplied through:

- `ADMIN_USERNAME`
- `ADMIN_PASSWORD`
- optional `ADMIN_SUPER_USERNAME`
- optional `ADMIN_SUPER_PASSWORD`

There are no hard-coded production admin passwords.

If the primary admin credentials are missing, admin access fails closed and returns HTTP 503.

Admin authentication is protected against brute-force attempts:

- maximum 5 failed authentication attempts
- 15-minute window
- counters are isolated by client IP
- successful authentication resets the counter
- blocked requests receive HTTP 429

Known limitation:

The admin rate-limit state is currently stored in process memory. A future multi-worker or multi-instance deployment must use a shared rate-limit store such as Redis or infrastructure-level rate limiting.

## 3. Sessions and cookies

Flask session cookies use security-oriented settings including:

- `SESSION_COOKIE_SECURE` in production
- `SESSION_COOKIE_HTTPONLY = True`
- `SESSION_COOKIE_SAMESITE`, defaulting to `Lax`

Analytics consent is separate from required application/session cookies.

Analytics remains disabled until explicit user consent is recorded.

Users can reopen cookie settings and change their analytics preference.

Analytics consent expires after 180 days.

## 4. Analytics and tracking

BlackSeaConnect may use:

- Google Analytics 4
- Microsoft Clarity

Analytics scripts are not loaded before consent.

Privacy signals such as Global Privacy Control / Do Not Track are respected by the client-side analytics logic.

Advertising storage and advertising personalization are not enabled by the application analytics configuration.

## 5. Browser security headers

The application centrally applies baseline browser security headers:

- `X-Content-Type-Options: nosniff`
- `X-Frame-Options: SAMEORIGIN`
- `Referrer-Policy: strict-origin-when-cross-origin`
- `Permissions-Policy`
- `Strict-Transport-Security` in HTTPS production deployments
- `Content-Security-Policy-Report-Only`

HSTS is only emitted when:

- the application environment is production
- `SITE_URL` uses HTTPS

## 6. Content Security Policy

CSP is currently deployed in **Report-Only** mode.

It is not yet enforced because the current application still contains:

- inline scripts
- inline styles
- dynamic style attributes
- dynamic external provider image URLs

The detailed CSP audit and current policy are documented in:

`docs/CSP_REPORT_ONLY_AUDIT.md`

Before moving to enforcing CSP, inline JavaScript and CSS should be migrated to static assets, hashes, or nonces where practical, and external origins should be narrowed.

`unsafe-eval` is not permitted by the current policy.

## 7. HTTPS and proxy trust

Production must use HTTPS.

Proxy headers are only trusted when `TRUST_PROXY_HEADERS` is explicitly enabled.

`ProxyFix` is configured only when proxy trust is enabled.

This setting must only be enabled when the deployment architecture guarantees that forwarded headers are supplied by a trusted reverse proxy and cannot be spoofed directly by clients.

## 8. Logging and sensitive data

Application logs must not expose:

- passwords
- authentication headers
- session cookies
- API keys
- Stripe signatures
- access tokens
- private secrets

The application includes redaction logic for sensitive markers.

New logging code must follow the same rule.

## 9. Public forms

Public-facing forms use IP-based rate limiting to reduce automated abuse.

Current limits are implemented in application memory.

This is appropriate for the current pilot architecture but must be replaced or supplemented with shared/infrastructure rate limiting for horizontally scaled production deployments.

## 10. Data access and authorization

Access to owner, professional, admin, enterprise, and operational resources must rely on canonical IDs and authorization checks.

Display names, email addresses, or labels must not be used as authorization identities.

Any new route exposing private records or files must include an explicit authorization check.

## 11. File and attachment access

Private operational attachments must be protected by the same authorization rules as their parent records.

Admin attachment access is covered by admin authentication and its rate-limit protection.

Uploaded filenames and file handling must continue to use safe filename handling and controlled storage locations.

## 12. Payments

Stripe secrets and webhook secrets must remain outside source control.

Production deployments must validate Stripe environment configuration before enabling live payment functionality.

Payment redirects and external Stripe destinations must be explicitly allowed by security policy.

## 13. Backups and recovery

Before production launch, the deployment must define and test:

- database backup frequency
- backup retention
- restore procedure
- responsibility for recovery
- encryption and access control for backups

The repository includes tested SQLite backup and restore utilities: scripts/backup_database.py and scripts/restore_database.py. They use SQLite backup APIs and integrity checks, and forced restore creates a safety copy first.

A backup is not considered operational until a restore has been successfully tested.

## 14. Security incidents

For a suspected security incident:

1. Preserve relevant logs and timestamps.
2. Rotate affected secrets and credentials.
3. Disable compromised accounts or access paths.
4. Identify affected users and data.
5. Restore trusted application state if required.
6. Document the cause and remediation.
7. Review whether notification obligations apply.

## 15. Production launch checklist

Before production launch, verify:

- production `SECRET_KEY` is configured
- admin credentials are configured
- HTTPS is active
- `SESSION_COOKIE_SECURE` is enabled
- proxy trust matches the real deployment architecture
- debug mode is disabled
- production database path/storage is correct
- SMTP credentials are production-ready
- Stripe mode and keys match the intended environment
- analytics consent works before analytics scripts load
- CSP Report-Only violations are reviewed
- backups and restore are tested
- logs do not expose secrets
- demo/test credentials and demo data are not exposed unintentionally

## 16. Known security debt

Current known items requiring future work:

- migrate admin rate limiting to shared storage for multi-worker deployments
- migrate public-form rate limiting to shared/infrastructure storage
- reduce inline JavaScript and CSS
- move CSP from Report-Only to enforcing mode
- narrow broad CSP image origins where possible
- add centralized CSP violation reporting if useful
- complete and test backup/restore procedures
- periodically review dependencies and production configuration

## Related documentation

- `docs/CSP_REPORT_ONLY_AUDIT.md`
- `docs/STAGING_DEPLOYMENT.md`
