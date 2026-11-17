# Midtown upstream review: CIPP 11.4.0

Reviewed source on 2026-11-16:

- Previous upstream: `8971c3fc6601fdfd30a9a31b35cffdb1ab67163b` (`v11.2.1`).
- New upstream: `12880df920a71239122aeddaf2bd5ad7a1eb1974` (`v11.4.0`).
- Previous production: `0d6f4ffeaaf73dd1e4c9a3b55d87c8a74e8f4e6c`.

The pristine mirror was fast-forwarded using GitHub's native fork-sync API.
The automated preparation stopped on three conflicting files, so this
integration was reconciled by hand over the same upstream delta:

- `frontend/package.json` and `frontend/yarn.lock` take the newer upstream
  dependency set (Storybook 10.6.6, Next ^16.4.2, Vite 8.2.4, Vitest 4.1.12,
  DOMPurify ^3.4.17) and keep the Midtown DOMPurify resolution pins so
  transitive consumers stay on the patched release.
- `frontend/src/hooks/use-intune-policy-editor.js` takes upstream's template
  references and preserve-chosen-options logic, and keeps the Midtown guards
  that clear stale form errors and roll the choice back when required Intune
  definitions fail to load.

No other Midtown patch was dropped; the EWS application allow-list standard,
its tests, and the fork maintenance tooling are unchanged.

The local secret gate excludes the generated
`frontend/public/intune-definitions/` buckets from content scanning because the
generic username/password detector misreads their Apple proxy preference keys on
the single-line files. That exclusion is documented in `SECRET-SCANNING.md`, and
the GitGuardian App and CI checks still cover the files. One synthetic bearer
token in the new rate-limiter test was shortened because it also tripped the
detector.

## Permission changes

`backend/Config/SAMManifest.json` is identical to the previously integrated
source, so this update requests no new Graph or partner permissions. No tenant
consent or permission-update operation was executed as part of preparing this
integration.

## Behavior and migration review

[CIPP 11.3.0 release notes](https://github.com/CyberDrain/CIPP/releases/tag/v11.3.0)
add NinjaOne ticketing and key sync, Intune enrollment restrictions, a device
policy status report, the CA policy comparison tool, and large-estate caching
work.

[CIPP 11.4.0 release notes](https://github.com/CyberDrain/CIPP/releases/tag/v11.4.0)
add opt-in multi-partner support, non-human identity investigation pages, Global
Secure Access templates, more Intune reporting, and the Tenant Groups tenant
selector.

`backend/Config/FeatureFlags.json` adds two flags, both disabled by default:

- `MultiPartner` — upstream describes it as pre-alpha and not for production.
  It is user-toggleable, so operators must keep it off.
- `TenantGroupSelector` — user-toggleable; API requests that name a
  `tenantGroup` are refused while it is off.

There are no database schema migrations. New standards and baseline migrations
run only where an operator deploys them. This is a source review, not evidence
of production migration acceptance.

## Deployment acceptance

Require the backend, frontend, and release-container checks on the final
candidate and an operator decision on the changed behavior before merge:
merging can publish a candidate that infrastructure automatically deploys.

Infrastructure must record the currently deployed digest, verify the published
candidate's provenance and immutable digest, and check Azure image readback,
`/version.json` against the final production source SHA, and
`/api/setup/health`. An image rollback alone does not prove that application
state migrations are reversible. Production remains on the previous image until
the reviewed integration passes its gates and is promoted.

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

That deployment's digest remains the last recorded rollback target for the
11.2.1 source. The operator approved the major-version/default changes before
merge. This task did not manually grant permissions or execute tenant standards.
