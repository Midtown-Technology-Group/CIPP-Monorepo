# Midtown CIPP fork

CIPP combines PowerShell backend (`backend/`), Next.js frontend (`frontend/`), and container tooling (`build/`). Read [MTG_FORK_MAINTENANCE.md](MTG_FORK_MAINTENANCE.md), [CONTRIBUTING.md](CONTRIBUTING.md), and [SECURITY.md](SECURITY.md) before changing tenant administration, standards, permissions, or deployment behavior.

## Exact branch and artifact contract

Default `mtg-production` carries the reviewed Midtown patch stack. Feature PRs target it. `main` is the pristine `CyberDrain/CIPP:main` mirror: add no Midtown commits there. Preserve native fork synchronization and stop/reconcile through a PR when upstream updates conflict. Review upstream release notes, permission changes, and migrations.

Only `mtg-production` may publish a production candidate after backend, frontend, and release-container validation succeeds on the exact current SHA. The candidate has provenance attestation and a SHA tag; Azure deployment belongs to `bifrost-infra`, which selects/verifies an immutable image digest. Never deploy the moving `candidate` tag directly. Normal rollback restores the recorded prior digest; an upstream moving tag is an emergency escape hatch requiring a separate operator decision.

## Verification

Follow [.github/workflows/mtg-validate.yml](.github/workflows/mtg-validate.yml). With its Pester/PSScriptAnalyzer prerequisites, run `./backend/Tests/Invoke-CippTests.ps1 -CI` in PowerShell from root. Run `Invoke-ScriptAnalyzer -Path ./backend/Modules/CIPPStandards/Public/Standards -Recurse -Severity Error` and inspect failures.

In `frontend/`, run `yarn install --frozen-lockfile`, `node -e "JSON.parse(require('fs').readFileSync('src/data/standards.json'))"`, and `yarn test:unit --testTimeout=30000`. The required container lane builds `build/Dockerfile.release` without publishing; retain its build arguments and upstream registry contract.

Follow [.github/copilot-instructions.md](.github/copilot-instructions.md) for Conventional Commits, including breaking-change notation. Local validation does not authorize running standards against customer tenants, publishing images, or Azure deployment. Keep those operations separate with exact tenant/artifact/runtime evidence.

## Secret gate before publication

Before publishing the current PR branch, commit the complete candidate and run
`python3 -I scripts/secret_gate.py --base origin/mtg-production` (native Windows: `python -I`). Require exit 0;
missing tooling/authentication, scan errors and skipped scans block publication.
Then run the existing repository gates. Repeat after changing outgoing commits.
Push exactly the scanned HEAD. This PR scan covers the current branch against its
fetched intended base; other refs, multi-ref pushes and rewritten history require
`--pre-push` with Git's complete ref-update stream. Stop if any pushed ref is
uncovered. See [secret scanning](SECRET-SCANNING.md) for base selection, new branches,
pre-push input and prerequisites. Preserve GitGuardian App, CI and Gitleaks checks.

For a non-default PR target, fetch its destination and pass that exact ref to
`--base`; the remote default is not a substitute for a release/maintenance base.

The secret gate requires Python 3.11+ and approved ggshield >=1.56.1,<2.
