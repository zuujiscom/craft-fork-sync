// Cloudflare Worker (cron trigger every 15 min) that starts the Sync forks workflow.
// GitHub's own schedule is best-effort and skips most runs; this keeps the 15-minute pace.
// GITHUB_TOKEN is a Worker secret: fine-grained token for this repo with Actions read and write.

addEventListener("scheduled", (event) => {
  event.waitUntil(dispatch());
});

async function dispatch() {
  const res = await fetch(
    "https://api.github.com/repos/zuujiscom/craft-fork-sync/actions/workflows/sync.yml/dispatches",
    {
      method: "POST",
      headers: {
        Authorization: `Bearer ${GITHUB_TOKEN}`,
        Accept: "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "craft-fork-sync-cron",
      },
      body: JSON.stringify({ ref: "main" }),
    },
  );
  if (res.status !== 204) {
    throw new Error(`workflow dispatch failed: ${res.status} ${await res.text()}`);
  }
}
