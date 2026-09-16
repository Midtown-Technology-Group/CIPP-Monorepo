# Midtown CIPP Fork Maintenance

This public fork carries reviewed Midtown standards on top of stable upstream
CIPP releases. It does not deploy directly to Azure.

## Branch contract

- `main` is a pristine mirror of `CyberDrain/CIPP:main`. Do not add Midtown
  commits to it.
- `mtg-production` contains the reviewed Midtown patch stack and is the only
  branch allowed to publish a production candidate.
- Feature branches target `mtg-production` through pull requests.

The default branch is `mtg-production` so scheduled fork-maintenance workflows
run from the controlled branch. `MTG: Propose Upstream Update` fast-forwards the
`main` mirror with GitHub's upstream-sync API and opens an operator issue when
upstream advances. The Midtown organization prevents Actions from creating pull
requests, so an operator opens the PR from `main` into `mtg-production`. GitHub
creates the reviewed merge; automation does not manufacture unsigned commits.

## Image contract

Merges to `mtg-production` publish:

- `ghcr.io/midtown-technology-group/cipp-monorepo:sha-<12-char-sha>`
- the moving convenience tag `candidate`
- a GitHub build-provenance attestation

Azure must use the immutable digest printed in the workflow summary. Never
configure production to follow `candidate` or another moving tag. Building an
image is not deployment authorization.

## Upstream update review

For every upstream-update operator issue:

1. Review CIPP release notes, permission changes, migrations, and conflicts.
2. Confirm the Midtown standards and metadata remain present.
3. Require the backend, frontend, and release-container validation jobs.
4. Merge only after the patch stack is coherent.
5. Record the resulting image digest.
6. Promote the digest through the separate infrastructure cutover procedure.
7. Verify `/api/setup/health`, interactive sign-in, standards visibility, and a
   safe read-only tenant operation before considering the update complete.

Rollback means restoring the previously recorded image digest. The official
`ghcr.io/cyberdrain/cipp:latest` image remains the emergency upstream escape
hatch, but switching to a moving tag is not a normal rollback procedure.
