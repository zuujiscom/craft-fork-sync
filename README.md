# craft-fork-sync

Every 2 hours (private repo: ~750 of the 2,000 free Actions minutes a month), moves `main` of each zuujiscom fork in `repos.txt` forward to the newest
[storytold](https://github.com/storytold) `main` commit whose CI is green.

**Green** means the commit has at least one check, every check finished as success, skipped
or neutral, and nothing failed, was cancelled or is still running. Only commits that were
the tip of upstream `main` count (first-parent history, not commits from merged PR
branches), and a commit must be at least 10 minutes old so all its workflows have started.

Forks only ever fast-forward. If a fork's `main` has commits upstream doesn't have, it is
left alone and reported. Results are in [STATUS.md](STATUS.md) and in each run's log.
