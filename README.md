# craft-fork-sync

Keeps the zuujiscom forks of the [storytold](https://github.com/storytold) repos in
`repos.txt` up to date. Every 15 minutes (started by the Cloudflare Worker in
[cron-worker/](cron-worker/worker.js), because GitHub's own schedule skips most runs) it runs
[green-fork-sync](https://github.com/zuujiscom/green-fork-sync), which moves each fork's
`main` to the newest upstream commit whose CI checks all passed.

Results are in each run's summary and in [STATUS.md](STATUS.md), which is updated at most every
6 hours (straight away when an error appears or clears).
