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

The pristine `main` mirror is locked against ordinary contributions with
`allow_fork_syncing` enabled. It does not require linear history or signed
commits: upstream publishes merge commits and unsigned commits, and rewriting
them would violate the pristine-mirror contract. Keep force pushes and deletion
disabled and admin enforcement enabled. This mirror-only policy does not relax
the PR, signature, or validation requirements on `mtg-production`.

The default branch is `mtg-production` so scheduled fork-maintenance workflows
run from the controlled branch. `MTG: Synchronize Upstream` first fast-forwards
the pristine `main` mirror using GitHub's native fork-sync API. Production
records the last integrated upstream commit in `MTG_UPSTREAM_REVISION` because
a signed squash merge does not retain upstream ancestry. An unchanged revision
is a no-op. For a new revision, the workflow applies only the upstream delta
over the Midtown patch stack and prepares a ready-for-review PR. It never
writes directly to `mtg-production` or merges the PR automatically.

The update commit is signed through GitHub's `createCommitOnBranch` API; its
signature, parent, and exact prepared tree must verify before the PR opens.
Existing update branches and PRs are preserved. Conflicts, upstream rewinds,
ambiguous identities, unsupported changes, or updates over 500 files / 20 MiB
stop preparation and open or update an operator issue. These limits require
manual reconciliation, not a partial release.

The workflow explicitly dispatches full validation on prepared PR branches
because PRs created by `GITHUB_TOKEN` do not trigger ordinary Actions PR events.
Review release notes, permission/default changes, and migrations before merging
through the normal protected production PR lane. Only successful validation of
the final merged production SHA may publish a candidate. The publisher
independently waits for all three required checks on that exact current SHA.

## Image contract

Merges to `mtg-production` publish:

- `ghcr.io/midtown-technology-group/cipp-monorepo:sha-<12-char-sha>`
- the moving convenience tag `candidate`
- a GitHub build-provenance attestation

Azure uses the immutable digest discovered and verified by the scheduled
deployment workflow in `MTG-Thomas/bifrost-infra`. Production never follows
`candidate` or another moving tag directly. A failed version or health probe
restores the previously deployed exact digest.

## Upstream update review

When automation reports a conflict:

1. Reconcile the Midtown patch stack with upstream on a feature branch.
2. Review CIPP release notes, permission changes, and migrations.
3. Require the backend, frontend, and release-container validation jobs.
4. Update `MTG_UPSTREAM_REVISION` to the exact reconciled upstream commit and
   merge the repair through a normal pull request into `mtg-production`.
5. Re-run `MTG: Synchronize Upstream`; do not bypass the validation or
   digest-pinned deployment gates.

Rollback means restoring the previously recorded image digest. The official
`ghcr.io/cyberdrain/cipp:latest` image remains the emergency upstream escape
hatch, but switching to a moving tag is not a normal rollback procedure.
