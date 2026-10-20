#!/usr/bin/env python3
"""Fast-forward each zuujiscom fork's main to the newest storytold main commit whose CI is green.

Green means: the commit has at least one check run or commit status, every check run has
finished as success/skipped/neutral, and the combined commit status (if any) is success.
Commits with no checks, or with anything failed, cancelled or still running, are passed
over. The fork only ever moves forward (no force), so it never loses commits.

Uses the `gh` CLI for API calls: GH_TOKEN in CI, the local gh login otherwise.
"""
import argparse
import datetime as dt
import json
import os
import subprocess
import sys
import tempfile

UPSTREAM = "storytold"
FORK = "zuujiscom"
BRANCH = "main"
LOOKBACK = 40            # upstream commits to consider per run
MIN_AGE_MIN = 10         # give every workflow time to create its checks
GOOD = {"success", "skipped", "neutral"}


def api(path, method="GET", fields=None, ok_codes=False):
    cmd = ["gh", "api", "-X", method, path, "-H", "Accept: application/vnd.github+json"]
    for k, v in (fields or {}).items():
        cmd += ["-F" if isinstance(v, bool) else "-f", f"{k}={str(v).lower() if isinstance(v, bool) else v}"]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        if ok_codes:
            return None, (r.stdout + r.stderr).strip()
        raise RuntimeError(f"{method} {path}: {(r.stdout + r.stderr).strip()[:300]}")
    out = json.loads(r.stdout) if r.stdout.strip() else {}
    return (out, None) if ok_codes else out


def green(repo, sha):
    """Return (is_green, reason)."""
    runs = api(f"repos/{UPSTREAM}/{repo}/commits/{sha}/check-runs?per_page=100&filter=latest")["check_runs"]
    status = api(f"repos/{UPSTREAM}/{repo}/commits/{sha}/status")
    if not runs and status["total_count"] == 0:
        return False, "no checks"
    pending = [c["name"] for c in runs if c["status"] != "completed"]
    if pending:
        return False, f"{len(pending)} running"
    bad = [f'{c["name"]}={c["conclusion"]}' for c in runs if c["conclusion"] not in GOOD]
    if bad:
        return False, "not green: " + ", ".join(bad[:3])
    if status["total_count"] and status["state"] != "success":
        return False, f"status {status['state']}"
    return True, f"{len(runs)} checks green"


def push_with_git(repo, sha):
    """For copies GitHub doesn't link as forks: the commit isn't in their object store yet."""
    token = os.environ.get("GH_TOKEN") or subprocess.run(
        ["gh", "auth", "token"], capture_output=True, text=True, check=True).stdout.strip()
    with tempfile.TemporaryDirectory() as d:
        run = lambda *a: subprocess.run(["git", "-C", d, *a], check=True, capture_output=True, text=True)
        run("init", "-q", "--bare")
        run("fetch", "-q", f"https://github.com/{UPSTREAM}/{repo}.git", sha)
        run("-c", f"http.extraheader=AUTHORIZATION: basic "
            + __import__("base64").b64encode(f"x-access-token:{token}".encode()).decode(),
            "push", "-q", f"https://github.com/{FORK}/{repo}.git", f"{sha}:refs/heads/{BRANCH}")


def sync(repo, dry):
    fork_sha = api(f"repos/{FORK}/{repo}/commits/{BRANCH}")["sha"]
    listed = api(f"repos/{UPSTREAM}/{repo}/commits?sha={BRANCH}&per_page={LOOKBACK}")
    if listed[0]["sha"] == fork_sha:
        return "up to date", fork_sha, None
    # Only commits that were themselves the tip of main: follow first parents from the head.
    # The plain list also holds commits from merged PR branches, which main never pointed at.
    by_sha, commits, cur = {c["sha"]: c for c in listed}, [], listed[0]
    while cur:
        commits.append(cur)
        parents = cur["parents"]
        cur = by_sha.get(parents[0]["sha"]) if parents else None
    now = dt.datetime.now(dt.timezone.utc)
    notes = []
    for c in commits:
        sha = c["sha"]
        if sha == fork_sha:
            break
        when = dt.datetime.fromisoformat(c["commit"]["committer"]["date"].replace("Z", "+00:00"))
        if now - when < dt.timedelta(minutes=MIN_AGE_MIN):
            notes.append(f"{sha[:8]} too new")
            continue
        ok, why = green(repo, sha)
        if not ok:
            notes.append(f"{sha[:8]} {why}")
            continue
        cmp = api(f"repos/{UPSTREAM}/{repo}/compare/{fork_sha}...{sha}")
        if cmp["status"] != "ahead":
            if api(f"repos/{UPSTREAM}/{repo}/compare/{fork_sha}...{commits[0]['sha']}")["status"] != "ahead":
                return "fork has diverged from upstream main, not touching it", fork_sha, None
            notes.append(f"{sha[:8]} not a fast-forward")
            continue
        if dry:
            return f"would move {cmp['ahead_by']} commits to {sha[:8]} ({why})", fork_sha, sha
        _, err = api(f"repos/{FORK}/{repo}/git/refs/heads/{BRANCH}", "PATCH",
                     {"sha": sha, "force": False}, ok_codes=True)
        if err:
            if "Object does not exist" not in err and "422" not in err:
                raise RuntimeError(err[:300])
            push_with_git(repo, sha)
        return f"moved {cmp['ahead_by']} commits to {sha[:8]} ({why})", fork_sha, sha
    return "waiting: no newer green commit (" + "; ".join(notes[:3]) + ")", fork_sha, None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--status", help="write a Markdown status table here")
    ap.add_argument("repos", nargs="*")
    a = ap.parse_args()
    repos = a.repos or [l.strip() for l in open(os.path.join(os.path.dirname(__file__), "repos.txt"))
                        if l.strip() and not l.startswith("#")]
    rows, failed = [], 0
    for repo in repos:
        try:
            result, before, after = sync(repo, a.dry_run)
        except Exception as e:  # keep going with the other repos
            result, before, after, failed = f"ERROR {e}", "", None, failed + 1
        print(f"{repo:24} {result}", flush=True)
        rows.append((repo, (after or before)[:8], result))
    if a.status:
        with open(a.status, "w") as f:
            f.write("# Fork sync status\n\n| repo | zuujiscom main | last result |\n|---|---|---|\n")
            for repo, sha, res in rows:
                f.write(f"| [{repo}](https://github.com/{FORK}/{repo}) | `{sha}` | {res.split(' (')[0]} |\n")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
