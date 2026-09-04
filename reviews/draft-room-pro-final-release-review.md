# Draft Room Pro 2026
## Final Release Review of `DraftroomProDeploy.zip`

**Review date:** September 3, 2026  
**Files reviewed:** `index.html`, `index.js`, `wrangler.toml`, `espn-draft-watch.py`, `README.md`, and `DEPLOY.md`  
**Design decision:** The visual design is accepted and treated as frozen. This review addresses correctness, live ESPN synchronization, recommendation logic, packaging, deployment, failure recovery, and draft-night readiness.

---

# 1. Executive verdict

This is the strongest version of the project so far. Several previously identified architectural problems have been fixed correctly:

- standard browser persistence now works through `localStorage`;
- the recommendation engine no longer changes when the user toggles the visual Value sort;
- player survival is conditioned on the fact that the player is still available now;
- the advisor distinguishes a forecast from an actual on-the-clock recommendation;
- all normal "draft to my team" UI paths now pass through a central turn guard;
- FLEX vacancies are included in endgame forced-fill logic;
- static roster caps were replaced with league-derived caps;
- ESPN snapshots are reconciled as whole snapshots rather than naïve event increments;
- repeated identical snapshots are idempotent;
- unmatched ESPN selections now advance the internal draft clock;
- player identity resolution fails closed rather than pretending a fallback exists;
- the browser poller now has a timeout and a single-flight guard;
- ESPN credentials remain on the Worker rather than in GitHub Pages.

The project is therefore no longer in prototype territory.

However, the supplied archive is **not yet a deploy-and-use release**. There are two separate conclusions:

## Manual board

**Nearly ready.** The manual board can be published after correcting the archive layout and GitHub Pages instructions.

## Live ESPN mode

**Not ready for a real draft yet.** A small number of remaining state-authority and UI defects can silently make the live board wrong while it appears healthy.

The highest-priority remaining issue is no longer the recommendation formula. It is ensuring that:

```text
ESPN snapshot
+ manual fallback
+ identity map
+ visible clock
+ roster counts
```

always converge to one unambiguous state.

---

# 2. What I actually tested

## 2.1 Static and syntax checks

| Check | Result |
|---|---|
| `python3 -m py_compile espn-draft-watch.py` | PASS |
| `node --check index.js` | PASS |
| Extracted inline JavaScript from `index.html` and ran `node --check` | PASS |
| Duplicate HTML IDs | PASS: none |
| JavaScript `el("...")` references to missing static IDs | PASS: none |
| Credential-shaped value scan | PASS: no actual ESPN credentials found |
| ZIP inventory versus documented directory tree | FAIL |
| Wrangler entry point exists at configured path | FAIL |

## 2.2 Logic-harness results

| Scenario | Result |
|---|---|
| Toggle Value mode and compare advisor ranking | PASS: recommendation list unchanged |
| Apply the same ESPN snapshot twice | PASS: second application is a no-op |
| Correct a normal feed-owned pick | PASS |
| Manually enter a pick, then receive identical ESPN confirmation | PASS: provenance becomes feed-owned |
| Receive an unmatched ESPN pick | PASS: change result includes clock/unmatched state |
| Decimal ADP such as `27.4` | FAIL: decimal is ignored and the bye value becomes ADP |
| Refresh rankings after a manual column reorder | FAIL: order is reset |
| Queue a curated sleeper | FAIL: the sleeper grade can be removed |
| Migrate an older saved player lacking `offBoard` | FAIL |
| Reload with a persisted ESPN ID map and live mode enabled | FAIL: runtime map is not restored |
| Manual player and different ESPN player assigned to the same pick | FAIL: both remain on the user's roster at one pick |
| User drafts an out-of-board ESPN player | FAIL: draft clock advances, but roster count and lineup needs do not |
| Validate a `LINEAR` draft type | FAIL: accepted even though all pick math is snake |
| Feed badge present in static interface | FAIL |
| Feed badge click included in delegated click selector | FAIL |
| Worker configured with only one private-league cookie | FAIL closed: no; it silently behaves as public |

## 2.3 Board depth

The bundled player pool contains:

| Position | Players |
|---|---:|
| QB | 16 |
| RB | 38 |
| WR | 52 |
| TE | 21 |
| K | 15 |
| DST | 14 |
| **Total** | **156** |

The default roster configuration is 12 teams × 16 roster spots = **192 selections**.

Therefore, out-of-board ESPN selections are not rare edge cases. They are guaranteed if the league fills all default roster spots from a normal player pool.

---

# 3. Release blockers

These should be treated as **P0**.

---

## P0-1. The ZIP layout does not match either guide

The archive contains six files at the root:

```text
DEPLOY.md
README.md
index.html
index.js
wrangler.toml
espn-draft-watch.py
```

The documentation says the user should see:

```text
site/
worker/
tools/
research/
docs/
.gitignore
```

Those directories and several listed files are absent.

As a result, these documented commands fail:

```bash
cd site
cd worker
python3 tools/espn-draft-watch.py
```

The README also refers to files that are not in the archive, including a fallback board and research report.

### Required correction

Either:

1. package the files in the documented structure; or
2. rewrite the documentation around the flat archive.

The corrected deployment runbook supplied with this review uses the first and cleaner option.

---

## P0-2. GitHub Pages cannot publish from `/site` in branch mode

Both guides tell the user to select:

```text
main /site
```

GitHub's branch-based Pages publisher supports only:

```text
/(root)
/docs
```

The recommended layout is therefore:

```text
docs/index.html
```

with Pages configured as:

```text
main /docs
```

Alternatively, use a GitHub Actions Pages workflow. That is unnecessary for this single-file site.

---

## P0-3. The Worker entry point does not exist

`wrangler.toml` contains:

```toml
main = "src/index.js"
```

but the archive contains:

```text
index.js
```

at the root.

A deployment from the supplied folder cannot resolve the configured entry point.

### Required correction

Recommended:

```text
worker/
  src/
    index.js
  wrangler.toml
  package.json
  package-lock.json
```

The corrected runbook includes the exact commands.

---

## P0-4. The live-feed badge is never inserted

The code has:

- CSS for `.feed`;
- `feedBadgeHTML()`;
- `setFeed()` that replaces `#feed`;
- documentation describing badge states.

But there is no static element with:

```html
id="feed"
```

in the top console.

`setFeed()` therefore does this forever:

```js
const n = document.getElementById("feed");
if (n) n.outerHTML = feedBadgeHTML();
```

Since `n` is always null, the badge never appears.

This removes the user's primary indication of:

- Manual;
- Connecting;
- Live;
- Stale;
- Suspicious;
- Auth error;
- Config error;
- Complete;
- unmatched-pick count.

That is a live-operation blocker.

### Required correction

Insert an initial badge button in the console, for example:

```html
<button class="feed"
        id="feed"
        data-feed="off"
        data-openfeed="1"
        title="Live ESPN feed">
  <i class="fdot"></i>
  Manual
</button>
```

Place it next to Setup or before the other console tools.

---

## P0-5. The badge's click handler is unreachable

The event handler contains:

```js
if (t.dataset.openfeed) {
  el("cfg").click();
  return;
}
```

but the `closest()` selector does not include:

```text
[data-openfeed]
```

Even after the badge is inserted, clicking it will not reach that branch.

### Required correction

Add `[data-openfeed]` to the delegated selector.

---

## P0-6. Live mode does not resume after a page reload

Identity resolution stores the map twice:

```js
feed.idMap = map;
state.espnIdMap = map;
```

`state.espnIdMap` is persisted.

On boot, however, `startFeed()` checks only:

```js
feed.idMap
```

The runtime field starts as null after every page reload.

Result:

```text
Config error:
Identity map unavailable — live mode not armed.
```

even though the map is present in saved state.

This contradicts the documented self-healing/reload behavior.

### Required correction

During migration or boot:

```js
feed.idMap = state.espnIdMap || null;
```

Also validate that every mapped board ID still exists. If the build or seed changed, force a fresh identity resolution.

A stronger long-term design stores a schema/build fingerprint with the map.

---

## P0-7. Manual and ESPN picks can occupy the same overall pick

Reproduced state:

```text
manual Player A:
  mine
  pickNo 3
  feed false

ESPN snapshot:
  Player B
  team = my team
  overall 3
```

After reconciliation, both remain:

```text
Player A: mine at pick 3
Player B: mine at pick 3
```

`myPicksMade()` reports two roster selections from one actual slot.

This can distort:

- roster counts;
- picks remaining;
- positional needs;
- endgame forced filling;
- recommendation scores;
- the My Team rail.

### Root cause

Manual state is stored directly on the same player fields as authoritative feed state, but unconfirmed manual marks are preserved indefinitely.

### Required authority model

While a healthy ESPN snapshot is available:

```text
ESPN owns:
- overall picks
- drafted players
- team ownership
- current pick
```

Manual selections should be **provisional events**, not permanent competing truth.

Recommended reconciliation:

1. manual action creates a provisional pick;
2. if ESPN later confirms it, convert it to feed-owned;
3. if ESPN reaches that overall pick with a different player, clear the provisional mark and surface a correction;
4. if the feed is stale, provisional picks may temporarily drive the UI;
5. when a healthy snapshot returns, ESPN wins.

At minimum, reject two players sharing one pick and surface a conflict rather than keeping both.

---

## P0-8. `manualMax` can keep the clock ahead of healthy ESPN

Current clock logic:

```js
state.nextPick = Math.max(
  s.draft.nextOverallPick || 1,
  manualMax + 1
);
```

This means a mistaken or stale manual mark can permanently prevent the board from returning to the authoritative ESPN clock.

Whole-snapshot reconciliation is only truly self-healing if a healthy snapshot can correct chronology.

### Required correction

Separate:

```text
authoritative ESPN next pick
provisional manual next pick
display next pick
```

Suggested policy:

```text
feed healthy:
  current pick = ESPN

feed stale/disconnected:
  current pick may advance from provisional manual state
```

Do not let manual chronology silently outrank a healthy feed.

---

## P0-9. An out-of-board pick by the user does not count toward the roster

Unmatched selections correctly advance the clock now.

But if the unmatched ESPN pick belongs to the user's team:

```js
myPicksMade()
myCounts()
picksLeft()
lineupHoles()
```

do not see it, because no board player was marked `mine`.

With 156 board players and a 192-pick default draft, this is likely late in the draft.

### Consequences

The engine may believe:

- the user has more picks remaining than they really do;
- a position is still empty when the user drafted an out-of-board player there;
- K/DST or FLEX must still be forced;
- the roster can accept another player after it is full.

### Required correction

Preserve metadata for every ESPN selection, not only mapped board players.

At identity-resolution time, store an ESPN player catalog:

```js
state.espnPlayersById[playerId] = {
  name,
  pos
};
```

Then store external picks:

```js
state.externalPicks = [
  {
    overall,
    playerId,
    teamId,
    mine,
    name,
    pos
  }
];
```

Roster calculations must include the user's external picks.

Expanding the curated board to at least 220–250 players reduces this problem but does not eliminate the need for correct external-pick accounting.

---

## P0-10. League-size mismatch is detected and then overwritten

`pollOnce()` does this:

```js
setFeed("suspicious", "ESPN reports ... teams");
```

but continues and shortly afterward does:

```js
setFeed("live", "... picks synced.");
```

The warning disappears.

The snapshot is still applied using the locally configured team count, so all snake-turn calculations may be wrong.

### Required correction

Fail closed:

```js
if (ESPN team count !== configured team count) {
    stop live application;
    set Config error or Suspicious;
    preserve last good state;
    require correction;
    return;
}
```

Also verify that the selected `myTeamId` exists in the current snapshot before arming live mode.

A team selected from a previous league or adapter URL must not be accepted silently.

---

## P0-11. Auction/keeper/linear rejection is not actually implemented

The deployment guide says:

> Auction and keeper leagues are rejected.

That statement is not supported by the current normalized Worker contract.

The Worker requests `mSettings` but discards the useful league/draft metadata.

The browser:

- detects auction only after it sees a positive `bidAmount`;
- accepts a `LINEAR` draft type even though `isMyPick()` always reverses every round;
- never checks `keeperCount`;
- usually receives no `s.league` block at all.

### Required correction

The Worker should normalize league metadata from the actual ESPN response, for example:

```json
{
  "league": {
    "size": 12,
    "draftType": "SNAKE",
    "keeperCount": 0,
    "pickOrder": []
  }
}
```

The browser should accept only the formats it truly supports.

For the present product:

```text
draftType must be SNAKE
keeperCount must be 0
team count must match
```

Reject `LINEAR`, auction, keeper, salary-cap, and unknown modes unless their behavior has been explicitly implemented and tested.

---

## P0-12. Disconnect does not abort or invalidate an in-flight poll

`AbortController` exists only as a local variable inside `pollOnce()`.

`stopFeed()`:

- clears the future timer;
- marks the feed stopped;
- sets `inFlight` false;

but cannot abort the current request and does not increment the response sequence.

A response that finishes after Disconnect can still:

- apply a snapshot;
- change the board;
- change the badge back to Live.

### Required correction

Store the controller:

```js
feed.abortController = ctl;
```

On stop:

```js
feed.stopped = true;
feed.seq++;
feed.abortController?.abort();
feed.abortController = null;
```

After the fetch resolves, recheck both:

```js
seq === feed.seq
!feed.stopped
cfg.enabled
```

before applying anything.

---

# 4. Important nonblocking defects

These are **P1**. Most should still be fixed before the actual draft.

---

## P1-1. Decimal ADP parsing is broken

The parser recognizes only:

```regex
^\d{1,3}$
```

A normal input row such as:

```text
1    Test Player    RB    TST    5    27.4
```

was parsed as:

```json
{
  "rank": 1,
  "bye": null,
  "adp": 5
}
```

The decimal `27.4` was ignored and bye week 5 was misclassified as ADP.

Since ADP powers survival probability, this is not cosmetic.

### Fix

Use a header-aware parser and permit decimals.

Do not infer all numeric meaning solely by relative position when headers are available.

---

## P1-2. The UI claims tier refresh works, but no tier is parsed

The Setup copy says:

> rank, ADP, tier, bye and team update in place

The parser returns no tier field, and `applyRankings()` never updates tier.

Either implement tier support or remove it from the claim.

---

## P1-3. Rankings refresh does not preserve column ordering

The deployment guide says:

> Your picks and your column ordering survive the refresh.

The code sorts every positional list by refreshed overall rank and rewrites `order`.

A manual swap was reversed by the test harness.

The product already defines manual order as display-only, which is sensible. It should therefore preserve that display preference independently:

```text
source overall rank
user display order
```

Do not overwrite one with the other.

---

## P1-4. Queue and sleeper state are incorrectly combined

Before the user's turn, Queue calls the same `toggleStar()` used for the sleeper pool.

For an existing A/B/C sleeper:

```text
Queue
```

can remove the curated sleeper grade.

These are different concepts.

Use:

```js
queued: boolean
sleeperGrade: "A" | "B" | "C" | null
starred: boolean
```

A player can be queued, starred, and a sleeper simultaneously.

---

## P1-5. `offBoard` migration is incomplete

Fresh seed records set:

```js
offBoard: ovr >= 999
```

Older saved records may not have the field.

`migrate()` does not populate it.

New players added by a rankings refresh also do not receive an explicit `offBoard` field.

### Fix

Prefer a real status field:

```js
eligibility:
  "active"
  "excluded"
  "suspended"
  "unknown"
```

At minimum, set or recalculate `offBoard` during:

- build;
- migration;
- rankings refresh;
- new-player insertion.

---

## P1-6. Undo can roll back authoritative feed state

Undo stores a full JSON snapshot before manual operations.

Scenario:

1. user stars a player;
2. ESPN advances several picks;
3. user presses Undo to remove the star;
4. the entire older state is restored, including the old draft clock and player statuses.

A later successful poll may heal it, but while stale or disconnected it can persist the rollback.

### Fix options

Best:

- store operation-level patches for manual actions.

Minimum:

- after undoing a manual change, immediately reapply `feed.lastGood` before rendering/saving;
- never allow undo to alter feed-owned fields.

---

## P1-7. The Worker silently accepts one cookie instead of both

The Python tool correctly treats:

```text
only SWID
or
only espn_s2
```

as configuration error.

The Worker sends a Cookie header only when both exist. If just one is configured, it silently makes a public request.

### Fix

Fail clearly when:

```js
Boolean(env.ESPN_SWID) !== Boolean(env.ESPN_S2)
```

For a private league, both are required.

---

## P1-8. `/api/players` errors are flattened

The Worker classifies every non-OK player-pool response as generic upstream failure.

The browser then tells the user that the route may not exist, even when the actual cause could be:

- authentication;
- rate limiting;
- wrong season;
- wrong configuration.

Return the same error classes used by `/api/draft`.

---

## P1-9. No automated regression tests are included

README says the reliability rules are "verified by tests," but the archive ships no test suite.

The fixes in this project are precisely the kind that regress during later edits.

Ship at least:

```text
tests/board-logic.test.js
tests/worker.test.js
```

with tests for:

- snapshot idempotency;
- corrections;
- duplicate picks;
- UI-sort invariance;
- conditional survival;
- external user picks;
- manual/feed conflicts;
- turn guard;
- reload;
- unsupported draft modes;
- parser formats.

---

## P1-10. Poll failures do not back off

The browser prevents concurrent polls and has a seven-second timeout, which is good.

But repeated failures continue at the same configured interval.

For 429, network failure, or ESPN instability, use exponential backoff with a ceiling.

Suggested behavior:

```text
healthy and far from user pick: 5–10s
near user pick:                 3–5s
on deck/on clock:               2–3s
failure:                        5, 10, 20, 30s
success:                        reset
```

---

## P1-11. No-ADP survival is displayed as false precision

Fallback probability is effectively constant by position category:

- K/DST around 97%;
- other unpriced players around 60%.

It does not vary meaningfully with the time horizon.

A player should not have the same survival probability two picks away and 100 picks away.

Use:

```text
N/A
```

unless there is market data, or derive a documented fallback distribution.

---

## P1-12. Forecast scoring is not fully conditioned on the upcoming user pick

The card now correctly displays:

```text
probability the player reaches my upcoming pick
```

But the internal wait calculation is still largely scored from the present state to the user's following turn.

A pre-turn forecast should separate:

```text
P(reaches upcoming user pick | available now)
```

from:

```text
P(reaches following user pick | reached upcoming user pick)
```

The clean label is:

```text
IF AVAILABLE AT 1.03
```

and the recommendation score should represent the decision as of 1.03.

---

## P1-13. The weighted score still double-counts source rank

These terms are highly correlated:

```text
base value
VOR
urgency
tier cliff
```

All are derived largely from the same exponential transformation of overall rank.

Then the total is multiplied by need.

This can create a precise-looking score whose components are not independent evidence.

Before tuning more weights, compare:

1. source ranking;
2. VOR only;
3. VOR + conditional VONA;
4. current weighted model.

Only retain extra terms if replay/backtesting shows an improvement.

---

## P1-14. Early roster need may double-count league demand

League demand is already reflected in replacement level.

The need multiplier then separately boosts positions with more unfilled dedicated slots.

At the beginning of a 3-WR/2-RB league, WR receives an additional need advantage after WR replacement scarcity has already been modeled.

Consider keeping the need multiplier near 1.0 until roster construction becomes a genuine constraint late in the draft.

---

## P1-15. VONA should use marginal value above replacement

Current urgency is approximately:

```text
current raw value - expected future raw value
```

A cleaner measure is:

```text
current marginal value above replacement
-
expected future marginal value above replacement
```

This prevents the wait penalty from extending below replacement and reduces overlap between VOR and urgency.

---

## P1-16. FLEX shares remain fixed heuristics

The model still allocates FLEX demand as:

```text
45% RB
45% WR
10% TE
```

This is a reasonable temporary assumption, not a league-derived result.

A stronger replacement model fills dedicated starters first, then fills the league-wide FLEX pool from the best remaining eligible marginal values.

---

## P1-17. Canonical identity is still synthetic board ID

The live map is:

```text
ESPN ID -> p1/p2/p3
```

That works only while seed order remains stable.

Long term:

```text
id = espn:<playerId>
```

for ESPN players, with:

```text
custom:<UUID>
```

for user-created players.

Names should not be identity, and seed insertion should not invalidate persisted maps.

---

## P1-18. The curated board is too shallow for the default league

Increase to at least:

```text
220–250 players
```

for a 192-pick draft.

Also distinguish:

```text
out-of-board selection
```

from:

```text
identity mismatch
```

An ESPN player outside a deliberately curated top 250 is not necessarily a data-quality failure.

---

## P1-19. Scoring format is implicit

The user can change lineup slots but not scoring settings.

The player rankings appear to encode a specific scoring format, while the engine does not expose:

- PPR;
- passing TD value;
- bonuses;
- superflex;
- TE premium.

That is acceptable for one known personal league, but the supported format should be written explicitly.

Changing starting WR count does not convert half-PPR data to full PPR.

---

# 5. Worker assessment

The Cloudflare Worker architecture is still the correct design for this project.

## Good

- credentials are server-side;
- current ESPN read hostname is used;
- `/api/draft` and `/api/players` are separated;
- responses are normalized;
- error bodies do not expose cookies;
- CORS origin is configurable;
- short edge caching reduces repeated upstream requests;
- no fantasy decision logic is placed in the proxy.

## Remaining Worker changes

Before real use:

1. validate both-or-neither cookie configuration;
2. normalize league size, draft type, keeper count, and pick order;
3. classify `/api/players` errors correctly;
4. add an upstream timeout;
5. fail if malformed picks are skipped during an active draft rather than silently continuing;
6. add unit tests.

The public Worker endpoint remains callable by anyone who knows the URL. CORS controls browsers; it is not authentication. The project documentation already acknowledges this tradeoff.

---

# 6. Python diagnostic-client assessment

`espn-draft-watch.py` remains useful as a pre-deployment diagnostic.

## Good

- syntax passes;
- standard library only;
- correct ESPN host;
- normalized contract;
- atomic output;
- classified auth/config/rate-limit failures;
- retry/backoff;
- private cookie validation;
- player IDs preserved.

## Minor remaining issue

Console "new pick" tracking should key on:

```text
overall pick + player/team fingerprint
```

rather than only overall pick.

Otherwise a corrected selection at the same overall number updates the JSON snapshot but may not be announced in console output.

For machine streaming, use NDJSON rather than successive pretty-printed JSON documents. The documented one-shot check is unaffected.

---

# 7. Documentation corrections

The supplied `DEPLOY.md` should not be used unchanged.

Correct these statements:

| Current instruction/claim | Correction |
|---|---|
| Archive contains `site/`, `worker/`, `tools/` | It is flat; restructure it |
| Pages source can be `/site` | Use `/docs`, root, or Actions |
| `macOS ships with Python` | Check `python3 --version`; do not assume |
| Node `v18 or higher` | Use a supported LTS release, preferably Node 24 or 22 |
| Generate a classic PAT with broad `repo` scope | Prefer GitHub CLI, Git Credential Manager, SSH, or a fine-grained token |
| Run `wrangler deploy` after each `secret put` | `wrangler secret put` deploys a new Worker version immediately |
| `npm create cloudflare@latest` inside this existing project | Unnecessary; install Wrangler locally in the provided Worker folder |
| Your column order survives ranking refresh | It currently does not |
| Auction and keeper leagues are rejected | Not reliably true until league metadata is normalized and validated |
| Badge turns Live | No badge is currently mounted |
| Reload self-heals live mode | Runtime ID map is currently lost on reload |
| GitHub Pages is unlimited | It has documented soft and size/build limits, although this project is far below them |

---

# 8. Go/no-go decision

## Deploy manual mode now?

**GO after repackaging and corrected Pages setup.**

The manual interface, persistence, search, turn guard, roster rail, and advisor are usable.

## Deploy Worker for development?

**GO after fixing the entry-point path.**

It can be deployed and tested without putting secrets in the frontend.

## Rely on live ESPN mode in the real draft?

**NO-GO until the following pass:**

- visible/clickable feed badge;
- saved identity map restored on reload;
- ESPN/manual conflict resolution;
- external user picks included in roster accounting;
- team count mismatch fails closed;
- selected team validated against every snapshot;
- snake/redraft metadata validated;
- in-flight request aborted/invalidated on disconnect;
- exact deployed Worker and Pages URLs tested through a real ESPN draft rehearsal.

## Recommendation engine release status

**BETA.**

Its structure is thoughtful and transparent, but score calibration still needs replay comparison against a simpler VOR + conditional VONA baseline.

---

# 9. Minimum fix order

## Pass A — deployment blockers

1. Repackage into `docs/`, `worker/src/`, and `tools/`.
2. Configure Pages as `main /docs`.
3. Install local Wrangler and generate `worker/package.json`.
4. Verify `worker/src/index.js` matches `wrangler.toml`.

## Pass B — live-state blockers

1. Mount the feed badge and fix its delegated selector.
2. Restore and validate `state.espnIdMap` on boot.
3. Replace `manualMax` authority with provisional-manual reconciliation.
4. Guarantee one player per pick and one pick per player.
5. Account for external picks, especially the user's.
6. Fail closed on league/team mismatch.
7. Normalize and validate draft type/keepers.
8. abort/invalidate active requests on Disconnect.

## Pass C — data integrity

1. Header-aware import;
2. decimal ADP;
3. real tier import or corrected copy;
4. preserve user order;
5. separate queue, star, and sleeper;
6. migrate eligibility state;
7. expand the player pool.

## Pass D — model calibration

Compare:

```text
source rank
VOR
VOR + conditional VONA
current weighted model
```

Then consider projections, room-aware survival, and a two-turn rollout.

---

# 10. Final conclusion

The project has crossed an important line: most of the earlier redesign advice is now implemented rather than merely described.

The interface should stay as it is.

The remaining work is concentrated in release engineering and state authority. It is not a broad rewrite.

Once the P0 list passes a real end-to-end rehearsal, this becomes a credible draft-night beta:

```text
static GitHub Pages interface
+
private Cloudflare ESPN adapter
+
whole-snapshot reconciliation
+
transparent deterministic advisor
+
manual fallback
```

Until then, deploy the board for manual use and treat the live feed as a test feature rather than the sole source of draft state.
