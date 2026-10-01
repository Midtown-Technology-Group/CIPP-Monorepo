# Midtown CIPP fork

CIPP combines PowerShell backend (`backend/`), Next.js frontend (`frontend/`), and container tooling (`build/`). Read [MTG_FORK_MAINTENANCE.md](MTG_FORK_MAINTENANCE.md), [CONTRIBUTING.md](CONTRIBUTING.md), and [SECURITY.md](SECURITY.md) before changing tenant administration, standards, permissions, or deployment behavior.

## Exact branch and artifact contract

Default `mtg-production` carries the reviewed Midtown patch stack. Feature PRs target it. `main` is the pristine `CyberDrain/CIPP:main` mirror: add no Midtown commits there. Preserve native fork synchronization and stop/reconcile through a PR when upstream updates conflict. Review upstream release notes, permission changes, and migrations.

Only `mtg-production` may publish a production candidate after backend, frontend, and release-container validation succeeds on the exact current SHA. The candidate has provenance attestation and a SHA tag; Azure deployment belongs to `bifrost-infra`, which selects/verifies an immutable image digest. Never deploy the moving `candidate` tag directly. Normal rollback restores the recorded prior digest; an upstream moving tag is an emergency escape hatch requiring a separate operator decision.

## Verification

Follow [.github/workflows/mtg-validate.yml](.github/workflows/mtg-validate.yml). With its Pester/PSScriptAnalyzer prerequisites, run `./backend/Tests/Invoke-CippTests.ps1 -CI` in PowerShell from root. Run `Invoke-ScriptAnalyzer -Path ./backend/Modules/CIPPStandards/Public/Standards -Recurse -Severity Error` and inspect failures.

In `frontend/`, run `yarn install --frozen-lockfile`, `node -e "JSON.parse(require('fs').readFileSync('src/data/standards.json'))"`, and `yarn test:unit --testTimeout=30000`. The required container lane builds `build/Dockerfile.release` without publishing; retain its build arguments and upstream registry contract.

Follow [.github/copilot-instructions.md](.github/copilot-instructions.md) for Conventional Commits, including breaking-change notation. Local validation does not authorize running standards against customer tenants, publishing images, or Azure deployment. Keep those operations separate with exact tenant/artifact/runtime evidence.
