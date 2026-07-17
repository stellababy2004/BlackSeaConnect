# Staging deployment

This guide describes a provider-neutral, containerized staging deployment. Staging uses SQLite and Stripe test mode. Never put credentials in the image, repository, command history, or logs.

## Prerequisites

- A container runtime capable of building Linux/amd64 or Linux/arm64 images
- A persistent volume that can be mounted read/write by container user `blacksea`
- An HTTPS staging hostname and TLS termination
- A Stripe account with test mode enabled
- A secret manager supplied by the deployment platform
- A backup destination outside the application container

## Environment variables

Use [.env.example](../.env.example) only as a list of variable names. Generate a unique `SECRET_KEY` of at least 32 random characters and inject all secrets at runtime.

Staging must set `APP_ENV=staging`, an absolute HTTPS `SITE_URL`, `DATABASE_PATH` on the mounted volume, `STRIPE_MODE=test`, and an explicit `TRUST_PROXY_HEADERS` value. Set `TRUST_PROXY_HEADERS=1` only when the app is behind a trusted reverse proxy that replaces forwarded headers. Use `SESSION_COOKIE_SECURE=1` and `SESSION_COOKIE_SAMESITE=Lax` unless the deployment has a reviewed cross-site cookie requirement.

When Stripe Connect is enabled, all three Stripe variables are required. Staging accepts only `sk_test_` and `pk_test_` keys. The webhook signing secret must begin with `whsec_`. Do not mix test and live credentials.

Production additionally requires `STRIPE_MODE=live`, matching live-mode keys if Stripe Connect is enabled, `MANUAL_FINANCE_ENABLED=0`, and `SESSION_COOKIE_SECURE=1`.

## Create the staging SQLite volume

Mount a persistent volume at `/app/data` and set:

```text
DATABASE_PATH=/app/data/blacksea_owner.db
```

The directory must exist and be writable by UID/GID assigned to the image's `blacksea` user. On the first deployment, run the existing schema initializer once with the same volume and environment:

```sh
flask --app app init-db
flask --app app validate-config
```

SQLite supports a single shared application volume, not multiple replicas with separate files. Keep staging at one application replica unless the persistence design changes.

## Stripe test webhook

Create a test-mode webhook endpoint for:

```text
https://staging.example.com/webhooks/stripe
```

Subscribe only to events currently handled by the application:

- `checkout.session.completed`
- `checkout.session.async_payment_succeeded`
- `checkout.session.async_payment_failed`
- `payment_intent.payment_failed`
- `charge.refunded`
- `charge.dispute.created`
- `account.updated`

Store the endpoint signing secret as `STRIPE_WEBHOOK_SECRET`. Verification is local cryptographic validation; health checks do not contact Stripe.

## Build and start

Build without secret build arguments:

```sh
docker build -t blackseaconnect:staging .
```

After mounting the volume and injecting environment variables, the image starts with:

```sh
gunicorn --config gunicorn.conf.py app:app
```

The default is two threaded workers, two threads per worker, and a 60-second timeout. Because SQLite serializes writes, increase concurrency only after load testing.

## Health checks

- `GET /health/live` returns `200` when the Flask process can serve requests. It performs no database or Stripe calls.
- `GET /health/ready` returns `200` only when configuration, SQLite read/write access, required tables, and structural Stripe settings are valid. It returns `503` otherwise.

Responses contain booleans/status only. They do not expose paths, keys, database contents, stack traces, or exception details. Use readiness for traffic admission and liveness for process restart decisions.

## Backup before deployment

Stop writes or place the service out of traffic, then use SQLite's online backup command against the mounted database:

```sh
sqlite3 /app/data/blacksea_owner.db ".backup '/backup/blacksea_owner-YYYYMMDD-HHMMSS.db'"
sqlite3 /backup/blacksea_owner-YYYYMMDD-HHMMSS.db "PRAGMA integrity_check;"
```

Copy the verified backup to durable storage outside the container and record the image tag and configuration version. Never bake a database backup into an image.

## Rollback

1. Remove the new instance from traffic.
2. Start the previously known-good immutable image with the previous environment configuration.
3. Re-run `/health/live` and `/health/ready` before restoring traffic.
4. Restore the pre-deployment SQLite backup only if the failed release changed data incompatibly. Keep the failed database copy for investigation.
5. Verify a non-destructive owner, professional, reservation, and Stripe test-mode workflow.

This package does not add schema migrations, so rollback normally means reverting the image and configuration while retaining the same SQLite volume.

## Promote configuration to production

Copy variable names and reviewed non-secret settings through the secret manager; do not copy staging secret values. Change `APP_ENV` to `production`, use an HTTPS production URL such as `https://blackseaconnect.com`, set `STRIPE_MODE=live`, and replace every Stripe value with its matching live-mode credential. Set `MANUAL_FINANCE_ENABLED=0` and `SESSION_COOKIE_SECURE=1`.

Validate production configuration in an isolated pre-start job, take and verify a backup, deploy the same tested image digest, initialize no new schema automatically, then admit traffic only after readiness succeeds. Never combine a test publishable key, live secret key, or webhook secret from a different Stripe endpoint.
