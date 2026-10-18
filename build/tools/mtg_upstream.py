"""Prepare upstream deltas without importing unsigned history into production."""
import argparse
import base64
import json
from pathlib import Path
import re
import subprocess
import sys
from urllib.parse import quote

MARKER = "MTG_UPSTREAM_REVISION"
PRODUCTION = "mtg-production"


def command(*args, data=None):
    """Run a bounded child process without exposing its environment or response bodies."""
    try:
        result = subprocess.run(args, input=data, capture_output=True, timeout=120)
    except subprocess.TimeoutExpired:
        raise RuntimeError(f"Command timed out: {args[0]} {args[1]}. Inspect readback before retrying.") from None
    if result.returncode:
        raise RuntimeError(f"Command failed: {args[0]} {args[1]}. Inspect the run before retrying.")
    return result.stdout


def git(*args, data=None):
    """Read or stage Git data in the caller's isolated checkout."""
    return command("git", *args, data=data)


def prepare(upstream_ref="origin/main"):
    """Stage only the delta since the recorded revision, preserving production history."""
    if git("status", "--porcelain").strip():
        raise RuntimeError("Refusing to prepare an update in a dirty checkout.")
    previous = Path(MARKER).read_text(encoding="utf-8").strip()
    if not re.fullmatch(r"[0-9a-f]{40}", previous):
        raise RuntimeError("Invalid recorded upstream revision.")
    source = git("rev-parse", "--verify", upstream_ref + "^{commit}").decode().strip()
    base = git("rev-parse", "HEAD").decode().strip()
    git("merge-base", "--is-ancestor", previous, source)
    if previous == source:
        return {"changed": False, "source_sha": source}

    patch = git("diff", "--binary", previous, source, "--", ".")
    if patch:
        git("apply", "--3way", "--index", "-", data=patch)
    Path(MARKER).write_text(source + "\n", encoding="utf-8")
    git("add", "--", MARKER)
    return {
        "changed": True,
        "source_sha": source,
        "previous_sha": previous,
        "base_sha": base,
        "tree_sha": git("write-tree").decode().strip(),
        "branch": "mtg/upstream-" + source[:12],
    }


def api(path, payload=None):
    """Call GitHub with the runner credential and accept empty dispatch receipts."""
    args = ["gh", "api", path]
    if payload is not None:
        args += ["--method", "POST", "--input", "-"]
    raw = command(*args, data=json.dumps(payload).encode() if payload is not None else None)
    return json.loads(raw) if raw.strip() else {}


def commit_payload(repository, update):
    """Encode the staged tree as a size-bounded, compare-and-set signed commit request."""
    additions, deletions = [], []
    changes = git("diff", "--cached", "--name-status", "--no-renames", "-z").decode().split("\0")
    for index in range(0, len(changes) - 1, 2):
        status, path = changes[index:index + 2]
        if status == "D":
            deletions.append({"path": path})
        elif status in ("A", "M"):
            additions.append({"path": path, "contents": base64.b64encode(git("show", ":" + path)).decode()})
        else:
            raise RuntimeError("Unsupported upstream file change; reconcile through an operator PR.")
    # Bound API uploads; a large release must be reconciled by an operator.
    if len(additions) + len(deletions) > 500:
        raise RuntimeError("Upstream update exceeds the automatic 500-file preparation limit.")
    payload = {
        "query": "mutation($input: CreateCommitOnBranchInput!) { createCommitOnBranch(input: $input) { commit { oid } } }",
        "variables": {"input": {
            "branch": {"repositoryNameWithOwner": repository, "refName": update["branch"]},
            "expectedHeadOid": update["base_sha"],
            "message": {"headline": "chore(upstream): prepare CIPP " + update["source_sha"][:12]},
            "fileChanges": {"additions": additions, "deletions": deletions},
        }},
    }
    if len(json.dumps(payload).encode()) > 20 * 1024 * 1024:
        raise RuntimeError("Upstream update exceeds the automatic 20 MiB preparation limit.")
    return payload


def ensure_validation(repository, branch, head):
    """Dispatch validation only when no run already exists for this exact source."""
    workflow = f"repos/{repository}/actions/workflows/mtg-validate.yml"
    runs = api(workflow + "/runs?branch=" + quote(branch, safe="") + "&head_sha=" + head + "&per_page=1")
    if not runs["workflow_runs"]:
        api(workflow + "/dispatches", {"ref": branch})


def verify_commit(repository, head, update):
    """Reject a commit unless its signature, tree, and sole parent match preparation."""
    commit = api(f"repos/{repository}/git/commits/{head}")
    if (
        not commit["verification"]["verified"]
        or commit["tree"]["sha"] != update["tree_sha"]
        or [parent["sha"] for parent in commit["parents"]] != [update["base_sha"]]
    ):
        raise RuntimeError("Published commit signature, parent, or exact tree did not verify.")


def publish(repository, update):
    """Create or reuse a verified update PR without modifying protected production."""
    if not update["changed"]:
        return update
    branch = update["branch"]
    owner = repository.split("/")[0]
    existing = api(f"repos/{repository}/pulls?state=open&base={PRODUCTION}&head=" + quote(owner + ":" + branch, safe=""))
    if existing:
        if len(existing) != 1:
            raise RuntimeError("Ambiguous upstream pull request identity.")
        if existing[0]["base"]["sha"] != update["base_sha"]:
            raise RuntimeError("Existing upstream PR base does not match prepared production.")
        head = existing[0]["head"]["sha"]
        marker = api(f"repos/{repository}/contents/{MARKER}?ref=" + head)
        if base64.b64decode(marker["content"]).decode().strip() != update["source_sha"]:
            raise RuntimeError("Existing upstream PR has an unexpected source marker.")
        verify_commit(repository, head, update)
        ensure_validation(repository, branch, head)
        return {**update, "pull_request": existing[0]["html_url"], "existing": True}

    current = api(f"repos/{repository}/branches/{PRODUCTION}")["commit"]["sha"]
    if current != update["base_sha"]:
        raise RuntimeError("Production advanced during preparation; do not publish stale work.")
    matches = api(f"repos/{repository}/git/matching-refs/heads/" + branch)
    if any(row["ref"] == "refs/heads/" + branch for row in matches):
        raise RuntimeError("Update branch already exists without an open PR; inspect before retrying.")
    payload = commit_payload(repository, update)
    api(f"repos/{repository}/git/refs", {"ref": "refs/heads/" + branch, "sha": current})
    response = api("graphql", payload)
    if response.get("errors"):
        raise RuntimeError("Signed commit creation failed; inspect branch readback before retrying.")
    head = response["data"]["createCommitOnBranch"]["commit"]["oid"]
    verify_commit(repository, head, update)
    body = (
        f"Prepare upstream `{update['previous_sha']}` to `{update['source_sha']}` over production `{current}`.\n\n"
        "Only the upstream delta is applied, preserving the Midtown patch stack without importing unsigned history. "
        "Review release notes, permission/default changes, migrations, and all required checks before merging. "
        "A merge can publish and automatically deploy an attested candidate.\n\n"
        f"Upstream changes: https://github.com/CyberDrain/CIPP/compare/{update['previous_sha']}...{update['source_sha']}"
    )
    pr = api(f"repos/{repository}/pulls", {
        "title": "chore(upstream): update CIPP to " + update["source_sha"][:12],
        "head": branch, "base": PRODUCTION, "body": body, "draft": False,
    })
    ensure_validation(repository, branch, head)
    return {**update, "pull_request": pr["html_url"], "head_sha": head}


def main():
    """Expose preparation locally and publication only with an explicit repository target."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--publish", metavar="OWNER/REPO")
    args = parser.parse_args()
    try:
        update = prepare()
        if args.publish:
            update = publish(args.publish, update)
        print(json.dumps(update))
    except (RuntimeError, OSError, ValueError, KeyError) as error:
        print(str(error), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
