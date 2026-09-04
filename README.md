# Draft Room

A fantasy football draft board with a deterministic recommendation engine and
an optional live ESPN feed. The board is a single static HTML file; the only
server-side component exists solely because ESPN sends no CORS headers.

**New here? Follow [DEPLOY.md](DEPLOY.md)** — step by step for macOS, with a
check after every step. About 35 minutes, most of it optional.

## Layout

```
README.md              this file
DEPLOY.md              step-by-step deployment for macOS
docs/
  index.html           the board — GitHub Pages publishes THIS folder
  fallback.html        previous build, no engine or feed
  .nojekyll            stops GitHub's Jekyll processor touching the file
worker/
  src/index.js         Cloudflare Worker: holds ESPN credentials, serves normalized JSON
  wrangler.toml        Worker config — NEVER put cookies here, it gets committed
  package.json
tools/
  espn-draft-watch.py  local diagnostic client, same schema as the Worker
research/
  2026-fantasy-football-draft-report.md
reviews/               design and review history
```

Point GitHub Pages at **branch `main`, folder `/docs`** — GitHub's branch-mode
publisher only offers `/(root)` or `/docs`, which is why the board lives there.

## Zero-cost hosting

- **GitHub Pages** — static, free, unlimited. Serves the board.
- **Cloudflare Workers free** — 100,000 requests/day, 10ms CPU. A three-hour
  draft polled every 3s is about 3,600 requests, so the adapter is free too.

## Why a proxy is required

ESPN's Fantasy API returns no `Access-Control-Allow-Origin` header, so a page
on `username.github.io` cannot call it from the browser regardless of how the
league is configured. Something server-side must make the request. That is the
Worker's entire job — it makes no fantasy decisions.

## Setup

### 1. Verify ESPN access before draft day

```bash
export ESPN_LEAGUE_ID=1234567
export ESPN_SEASON=2026
# Private leagues only, both or neither:
export ESPN_SWID='{XXXXXXXX-XXXX-XXXX-XXXX-XXXXXXXXXXXX}'
export ESPN_S2='AEB...'

python3 tools/espn-draft-watch.py --once --json
```

`401` means cookies are missing or stale. `404` means the league or season is
wrong. Do this days ahead, not on draft night.

> **Consider making your league public.** ESPN's *Make League Viewable to
> Public* setting removes the cookie requirement entirely. That deletes the
> only secret in the system and makes everything below simpler and more
> reliable — cookies expire, and they tend to expire at the worst moment.

### 2. Deploy the Worker

```bash
cd worker
npm create cloudflare@latest -- espn-draft-adapter   # then replace src/index.js
# Edit wrangler.toml: ESPN_LEAGUE_ID, ESPN_SEASON, ALLOWED_ORIGIN
npx wrangler secret put ESPN_SWID    # private leagues only
npx wrangler secret put ESPN_S2      # private leagues only
npx wrangler deploy
```

Check it: `curl https://espn-draft-adapter.<you>.workers.dev/api/draft`

### 3. Publish the board

Push to GitHub, enable Pages, and rename `draft-room-pro.html` to `index.html`
(or point Pages at it). Then in the board: **Setup → Live ESPN feed**, paste
the adapter URL, set your ESPN team id, and press **Connect**.

## How the live feed behaves

**Identity.** The board carries no ESPN IDs, so names are matched **once**, at
connect time, against `/api/players`. That builds an `espnId` map. Every poll
after that is integer set membership — no name matching during the draft.
ESPN IDs with no match on the board are shown in the badge as a data-quality
warning rather than silently dropped.

**Authority.** While the feed is healthy, ESPN owns picks, ownership and the
clock. A manual mark that ESPN later contradicts is released and you're told.
A manual mark ESPN hasn't reached yet survives. Undo is disabled while live.

**Three reliability rules**, each verified by tests:

1. **Whole-snapshot reconciliation, never event diffing.** Drafted state is
   derived from the complete pick list every poll, so missed polls, tab
   reloads and short outages self-heal with no special handling.
2. **A failed poll never un-drafts anyone.** On any error the last good
   snapshot stands and the badge goes stale.
3. **A pick-count regression is refused.** Fewer picks than last time during
   an active draft is far more likely to be a bad response than a rewound
   draft, so it's flagged rather than accepted.

Manual marking keeps working alongside the feed. Manual marks are tracked
separately and are never clobbered by a snapshot.

**Badge states:** `Manual`, `Connecting`, `Live 3s`, `Stale`, `Suspicious`,
`Auth error`, `Config error`, `Complete`.

## Design decisions worth knowing

**Your manual re-ranking is display only.** Dragging a player up a column
changes where you see him and nothing else — the advisor keeps scoring from the
published ranking. This keeps a single opinion in the model rather than two, and
stops a drag made as a note-to-self from quietly reweighting recommendations.
Starring works the same way: it files a player in the sleeper pool and does not
touch his score.

A column you have re-ordered shows a small `yours` marker in its header, so the
distinction between your view and the source order is never ambiguous. Enforced
by test: shuffling, reversing, colliding or deleting every stored order value
leaves recommendations, wait-costs and replacement levels byte-identical.

**The advisor will not draft on someone else's turn.** Before your pick the
panel reads `Projected · 1.03` with a Queue button and the odds the player even
reaches your slot. Space queues rather than drafts. Only when you are on the
clock does it become `The pick` with a Draft button.

**Survival is conditional.** Every candidate is known to be available right now,
so the model asks *P(reaches my next turn | still here)*, not the raw ADP curve.
A player who has fallen ten picks past his ADP is demonstrably falling, and the
unconditional curve ignored that evidence — it understated one real case by 5x.

## Security

- Cookies live only as Worker secrets. They are never in the Pages bundle,
  never in browser network traffic, never logged.
- `wrangler.toml` is committed; secrets go in with `wrangler secret put`.
- Set `ALLOWED_ORIGIN` to your Pages origin. CORS is a browser control, not
  authentication — for a personal board, a public-but-obscure endpoint
  returning only pick IDs is a reasonable risk, but know that's the tradeoff.
- If you ever add an LLM layer, route it through the Worker too. Never put an
  API key in the static site.

## Known unknowns

The ESPN Fantasy API is undocumented and can change without notice. The
hostname was verified 2026-09-03 against a live response returning
`currentSeasonId: 2026`, but the draft-specific behaviour is not something I
could test without a real league.

**Untested:** whether `mDraftDetail` updates promptly during a live draft.
ESPN's own draft room uses a push channel; the REST view may lag or may only
populate on commit. Verify with a mock draft before relying on it.

If the feed misbehaves on draft night, disconnect it. The board is fully
usable manually — search a name, press Enter, and it's off the board in about
two seconds.
