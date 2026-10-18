# Midtown upstream review: CIPP 11.2.1

Reviewed source on 2026-10-18:

- Previous upstream: `75dd35aec0e195537b6161778cb6d758a53ce954` (10.10.3).
- New upstream: `8971c3fc6601fdfd30a9a31b35cffdb1ab67163b` (`v11.2.1`).
- Previous production: `1a8860c796fc562454b7bd28ac95ac525a0a080b`.
- Previous deployed image: `ghcr.io/midtown-technology-group/cipp-monorepo@sha256:2899a535af5702a783ad350fc4bad350dbfb2f773c8df1dcec8620e8f5866b10`.

The pristine mirror was fast-forwarded using GitHub's native fork-sync API.
The production integration preserves the Midtown EWS application allow-list
standard and metadata. The lockfile conflict retains DOMPurify 3.4.16 and
ProseMirror View 1.42.6 instead of downgrading Midtown's security fixes.

## Permission changes

The upstream `backend/Config/SAMManifest.json` adds these requested permissions
relative to the previous production source. Names were resolved against the live
Entra service-principal permission definitions; this review does not grant them.

| Resource | Permission | Type |
| --- | --- | --- |
| Microsoft Graph | SecurityAlert.ReadWrite.All | Application |
| Microsoft Graph | DirectoryRecommendations.Read.All | Delegated |
| Microsoft Graph | SecurityAlert.ReadWrite.All | Delegated |
| Microsoft Graph | NetworkAccess.ReadWrite.All | Application |
| Microsoft Graph | NetworkAccessPolicy.ReadWrite.All | Application |
| ProjectWorkManagement | OrgSettings-Planner.ReadWrite.All | Application |

Permission consent and tenant-wide permission-update operations require a
separate explicit operator decision. No tenant standard or permission update
was executed as part of preparing this integration.

## Behavior and migration review

[CIPP 11.0.0 release notes](https://github.com/CyberDrain/CIPP/releases/tag/v11.0.0)
introduce Baselines as the replacement for classic Standards and Drift when the
feature is enabled. The integrated `FeatureFlags.json` additionally defaults
Baselines and Security Simulations on when `NoClassicStandards` is satisfied.
An explicit user toggle takes precedence. Old auto-seeded rows without a user
modification timestamp can be re-seeded under the new default. Production's
stored flags and classic-template inventory have not been inspected by this
source review.
Existing MCP beta clients may need their Azure configuration saved again and
the new connector URL, as described by upstream.

[CIPP 11.2.1 release notes](https://github.com/CyberDrain/CIPP/releases/tag/v11.2.1)
add ConnectWise breached-app filtering and alerts for application presence and
new service-principal credentials.

This is a major-version integration, not evidence of production migration
acceptance. Require the backend, frontend, and release-container checks on the
final candidate and an operator decision on the changed behavior before merge:
merging can publish a candidate that infrastructure automatically deploys.

## Deployment acceptance

Infrastructure must verify the published candidate's provenance and immutable
digest, retain the previous digest above, and check Azure image readback,
`/version.json` against the final production source SHA, and
`/api/setup/health`. An image rollback alone does not prove that application
state migrations are reversible. Production remains on the previous image
until the reviewed integration passes its gates and is promoted.

## Accepted deployment, 2026-10-18

PR #8 merged as `f8bbc3da89c3b8f02001d3ba9491961c436ea178` after backend,
frontend, release-container, CodeQL, and Sonar checks passed. Sonar's five
blocking imported findings were repaired; its exact-head security/reliability
issue count was zero before merge.

- [Validated image publication](https://github.com/Midtown-Technology-Group/CIPP-Monorepo/actions/runs/39129962318)
  published and attested
  `ghcr.io/midtown-technology-group/cipp-monorepo@sha256:44fb002427146ac2efb2f7542bd4462bf1f241f30a5909a4938fe2792d7a8865`.
- [Protected infrastructure deployment](https://github.com/MTG-Thomas/bifrost-infra/actions/runs/39131293210)
  verified the provenance, promoted the exact digest, and passed its version and
  health checks without rollback.
- Independent Azure and HTTP readback confirmed the same digest,
  `/version.json` commit `f8bbc3da89c3b8f02001d3ba9491961c436ea178`, and health
  `status=ok`, `ready=true`.

The previous digest above remains the recorded rollback target. The operator
approved the major-version/default changes before merge. This task did not
manually grant the new requested permissions or execute tenant standards.
