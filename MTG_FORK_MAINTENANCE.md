# Midtown CIPP Fork Maintenance

This public fork carries Midtown standards on top of upstream CIPP releases.
It publishes an attested candidate only after the complete production-fork
validation gate succeeds. Azure deployment remains owned by `bifrost-infra`.

## Branch contract

- `main` is a pristine mirror of `CyberDrain/CIPP:main`. Do not add Midtown
  commits to it.
- `mtg-production` contains the reviewed Midtown patch stack and is the only
  branch allowed to publish a production candidate.
- Feature branches target `mtg-production` through pull requests.

The default branch is `mtg-production` so scheduled fork-maintenance workflows
run from the controlled branch. `MTG: Synchronize Upstream` first fast-forwards
the pristine `main` mirror, then asks GitHub's native fork-sync API to merge the
same upstream release into `mtg-production`. A conflict stops the conveyor and
opens or updates an operator issue. A conflict-free update runs the full
validation gate; only a successful non-PR validation run may publish a new
candidate. The publisher independently waits for all three required checks on
the exact current `mtg-production` SHA before building it. GitHub creates and
verifies the upstream merge commit.

## Image contract

Merges to `mtg-production` publish:

- `ghcr.io/midtown-technology-group/cipp-monorepo:sha-<12-char-sha>`
- the moving convenience tag `candidate`
- a GitHub build-provenance attestation

Azure uses the immutable digest discovered and verified by the scheduled
deployment workflow in `MTG-Thomas/bifrost-infra`. Production never follows
`candidate` or another moving tag directly.

## Upstream update review

When automation reports a conflict:

1. Reconcile the Midtown patch stack with upstream on a feature branch.
2. Review CIPP release notes, permission changes, and migrations.
3. Require the backend, frontend, and release-container validation jobs.
4. Merge the repair through a normal pull request into `mtg-production`.
5. Re-run `MTG: Synchronize Upstream`; do not bypass the validation or
   digest-pinned deployment gates.

Rollback means restoring the previously recorded image digest. The official
`ghcr.io/cyberdrain/cipp:latest` image remains the emergency upstream escape
hatch, but switching to a moving tag is not a normal rollback procedure.
