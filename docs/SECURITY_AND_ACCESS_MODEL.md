# BININGA — Security & Access Constitution

This document defines the invariants that production code and CI must preserve.

## Identity and authority

- Exactly two designated identities can be permanent Owners.
- Owner identity is matched server-side from reserved email fingerprints.
- Owners cannot be created, deleted, demoted, or have their reserved email reassigned through collaborator APIs.
- Collaborators are created and managed by an Owner.
- A collaborator role never implies Owner status.

## Permission model

Owner receives every permission. Collaborators receive a role baseline plus Owner-managed grants/revocations.

Canonical permissions:

- `content.read`, `content.write`, `content.publish`
- `contacts.read`, `contacts.write`, `contacts.assign`
- `crm.read`, `crm.write`, `crm.export`
- `users.read`, `users.create`, `users.update`, `users.delete`
- `backup.read`, `backup.create`, `backup.download`
- `security.read`, `security.manage`
- `monitoring.read`, `monitoring.manage`
- `logs.read`
- `chatbot.manage`

Server authorization is authoritative. Hiding or showing controls in HTML/JavaScript is never considered a security boundary.

## Source of truth

- Production business state: persistent PostgreSQL/MySQL storage configured by `DATABASE_URL`/DB config.
- Owner identity policy: server policy code.
- Browser/session storage: cache/transport only, never business truth.
- `data.json`: seed/snapshot compatibility artifact, never the authoritative production write target.

## Persistence failure

Durable mutations fail closed if persistence is unavailable. A failed DB probe must never return a successful write acknowledgement.

A cached health probe and short circuit breaker prevent repeated slow failing writes during an outage.

## Compromised account response

- Password reset/change revokes prior sessions.
- Users can enumerate their own active sessions without receiving raw bearer tokens.
- Users can revoke every other active session.
- Owner-sensitive operations require Owner authorization; 2FA is expected for Owner accounts and must remain part of the authentication hardening roadmap/test surface.
- Security-relevant actions are audit logged.

## Backup and restore

- Backups include manifest metadata and SHA-256 integrity hashes.
- Restore must verify an archive before any mutation.
- Restore is Owner-only and must create a pre-restore safety backup first.
- Restore operations must be auditable.
- Point-in-time recovery is an infrastructure capability and must be enabled/verified with the production database provider separately.

## Deployment and rollback

1. CI must pass.
2. Create/verify a backup before destructive schema/data migrations.
3. Deploy immutable Git SHA.
4. Verify runtime health and production errors.
5. Code rollback uses the previous known-good Git/Vercel deployment.
6. Data rollback uses a verified backup/PITR; code rollback must never silently overwrite newer DB state.

## Test principle

Every security/business invariant that can be expressed deterministically should have an automated contract test. CI is expected to reject changes that weaken Owner cardinality, server-side authorization, persistence fail-closed behavior, reset token security, backup integrity, or architecture boundaries.
