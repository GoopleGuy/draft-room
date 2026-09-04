# Draft Room Pro 2026
## Final Full-Project Review

**Project reviewed:** `DraftRoomPro_Export.zip`  
**Files actually present in the export:**

- `draft-room-pro.html`
- `espn-draft-watch.py`
- `index.js`
- `README.md`

**Review date:** 2026-09-03  
**Design status:** treated as frozen. This review is about correctness, recommendation quality, ESPN synchronization, deployment, resilience, and draft-night operations.

---

# 1. Final verdict

This project has improved materially since the earlier review.

The board is no longer just an interactive ranking sheet. It now has:

- an explicit deterministic recommendation engine;
- source-rank value proxy;
- league-sensitive replacement levels;
- ADP survival estimates;
- conditional survival after a player has already fallen;
- VONA-style cost-of-waiting logic;
- lineup need and endgame forced-fill logic;
- explicit FLEX holes;
- derived roster caps;
- engine selectors separated from UI Value sorting;
- forecast mode before the user's pick;
- live ESPN snapshot reconciliation;
- localStorage fallback for GitHub Pages;
- a Cloudflare Worker that keeps ESPN credentials server-side;
- a local Python diagnostic client.

The design is good and should not be reopened.

The system is **close**, but I would not use the live-feed mode for a real draft until the P0 items below are corrected and exercised in an ESPN mock draft.

The biggest remaining risk is not the visual design or the basic recommendation formula.

It is **mixed-source draft state**: the live ESPN snapshot, manual marks, identity mapping, and the visible clock are not yet guaranteed to converge to one authoritative state.

---

# 2. Verification performed

I performed the following review/tests against the exported files.

## Static/code checks

- `python3 -m py_compile espn-draft-watch.py` — **PASS**
- `node --check index.js` — **PASS**
- extracted the `<script>` from `draft-room-pro.html`
- `node --check` on the extracted board JavaScript — **PASS**
- static HTML `id` versus `el("...")` reference check — **no missing static element IDs**
- secret-pattern scan — **no actual ESPN cookies/API keys found in the export**

## Logic harness checks

### PASS — UI Value sort no longer changes advisor results

The new `engineAvail()` selector successfully isolates the engine from `ui.byValue`.

Toggling Value mode returned the same ordered recommendation set.

This fixes a major prior defect.

### PASS — explicit off-board players are excluded from the engine

Josh Jacobs is now seeded with `offBoard: true`, and `engineAvail()` excludes him.

### PASS — conditional survival responds to observed falling

A player already surviving beyond ADP receives a materially higher conditional probability of continuing to fall than the old unconditional model.

### PASS — normal ESPN snapshot application is idempotent

Applying the same normalized snapshot twice produced no second state mutation.

### PASS — ordinary feed-owned pick correction works

Changing pick 1 from one ESPN player to another restored the old feed-owned player and assigned the corrected player.

### FAIL — manual mark later confirmed identically by ESPN does not become feed-owned

Reproduction:

1. manually mark Player A unavailable at pick 1;
2. ESPN later reports Player A at pick 1;
3. status and pick number already match;
4. `applySnapshot()` makes no mutation;
5. `p.feed` remains false.

A later ESPN correction removing Player A will therefore not restore him.

### FAIL — unmatched ESPN pick advances the internal clock but does not trigger render/save

Reproduction:

- valid ESPN snapshot contains one player not present in the board ID map;
- `state.nextPick` correctly changes from 1 to 2;
- `applySnapshot()` returns `changed = 0`;
- `pollOnce()` only calls `save(); render();` when `changed` is non-zero.

Result:

**the internal clock moves while the visible clock/advisor remains stale.**

This is not theoretical. See section 4.

### WARNING — no-ADP survival has no time-horizon sensitivity

Current K/DST survival:

```text
pick 2:   97%
pick 180: 97%
```

The same issue exists for manually added non-K/DST players at a constant 60%.

Those are placeholders, not probabilities.

---

# 3. Earlier issues that are now substantially fixed

These changes are good and should be retained.

## 3.1 GitHub Pages persistence

The board now detects:

1. Claude artifact `window.storage`;
2. normal browser `localStorage`;
3. memory-only fallback.

This fixes the previous GitHub Pages persistence problem.

### Minor cleanup

The comment says the backup key is "one write behind," but the implementation writes the **same blob** to the primary and backup keys.

That is duplicate redundancy, not a previous-version backup.

If a true rollback backup is desired:

```text
read current primary
write current primary to .bak
write new state to primary
```

This is not a release blocker.

---

## 3.2 Value-sort contamination

The engine now uses:

```js
engineAvail(pos)
```

rather than the UI-dependent `availIn()` when scoring candidates.

This is correct.

Add a permanent regression test:

> Advisor recommendations must not change when toggling Value, Notes, Taken, Compact, theme, or position tabs.

---

## 3.3 Conditional survival

The board now computes:

```text
P(survive to future | already survived to current)
```

rather than only unconditional survival from the original ADP curve.

This is the correct conceptual improvement.

---

## 3.4 Pre-turn advisor behavior

The advisor distinguishes:

- **The pick** when the user is actually on the clock;
- **Projected · X.XX** before the user's turn.

It also displays the chance the candidate reaches the upcoming user pick.

This is much safer than the old behavior.

---

## 3.5 Space-bar guard

Space no longer blindly drafts the recommendation before the user's turn.

Good fix.

There is still an incomplete centralization problem described below.

---

## 3.6 FLEX endgame holes

`lineupHoles()` now models FLEX explicitly.

This fixes the prior possibility of completing dedicated positions while still leaving FLEX unfilled.

---

## 3.7 Derived roster caps

The engine no longer uses the old hard-coded:

```text
QB 3 / RB 7 / WR 8 / TE 3
```

table.

`capFor()` now derives a cap from league settings and bench allocation.

This is directionally much better.

---

# 4. P0 — unmatched ESPN picks can freeze the visible clock

This is the clearest live-feed blocker.

## Why it is guaranteed to matter

The default league has:

```text
12 teams
16 roster spots per team
= 192 total draft selections
```

The board contains only:

```text
156 seeded players
```

Position counts:

```text
QB   16
RB   38
WR   52
TE   21
K    15
DST  14
---------
156
```

Therefore, even if identity resolution is flawless, a full default draft must contain players outside this board unless the draft ends early or the room drafts only this exact pool.

At least 36 selections cannot be represented by the current seed pool if all 192 roster slots are filled.

## Current failure

`applySnapshot()` does update:

```js
state.nextPick
```

even when the ESPN player ID is unknown.

But it returns only the count of changed **board player statuses**.

`pollOnce()` does:

```js
if (changed) {
  save();
  render();
}
```

Therefore an out-of-pool pick can:

- advance the internal clock;
- not update the displayed clock;
- not update the pick track;
- not recompute the advisor;
- not persist the new clock.

Late in the draft this can happen repeatedly.

## Required fix

A valid ESPN snapshot should update/render based on **snapshot state**, not only player status changes.

Simplest safe fix:

```js
const result = applySnapshot(s);
save();
render();
```

on every accepted new snapshot.

At three-second polling this board is small enough that rendering every accepted response is not a performance concern.

Or return structured change information:

```js
{
  playerChanged,
  clockChanged,
  unmatchedChanged,
  draftStateChanged
}
```

and render if any are true.

## Required regression test

Snapshot:

```json
{
  "draft": {
    "pickCount": 1,
    "nextOverallPick": 2,
    "inProgress": true
  },
  "picks": [
    {
      "overall": 1,
      "playerId": 99999999,
      "teamId": 7
    }
  ]
}
```

Expected:

```text
visible pick = 1.02
pick track advances
advisor recomputes
state persists
unmatched/out-of-pool count increments
```

---

# 5. P0 — identity-resolution failure fallback does not actually exist

The Connect flow says:

> Adapter has no `/api/players` route — matching lazily from picks instead.

and:

> Identity pre-resolve unavailable; the feed will still track picks it can match.

The draft snapshot, however, contains:

```text
playerId
teamId
overall pick
```

not player names.

`applySnapshot()` only looks up:

```js
map[pick.playerId]
```

There is no lazy name lookup in the live path.

## Failure scenario

Fresh browser:

```text
state.espnIdMap does not exist
```

Then `/api/players` fails.

The board still starts polling.

Every ESPN pick is now:

```text
unmatched
```

and no drafted player is removed from the board.

## Required fix

Pick one explicit policy.

### Preferred

**Do not enable live mode until identity resolution succeeds.**

Display:

```text
Identity map unavailable — live mode not armed.
```

Manual mode remains usable.

### Alternative

Have the Worker enrich normalized picks:

```json
{
  "playerId": 123,
  "name": "Player Name",
  "pos": "RB"
}
```

using a Worker-side cached player map.

The browser can then reconcile IDs and names.

### Alternative

Implement a real on-demand player lookup route.

Do not claim a lazy fallback that is not implemented.

---

# 6. P0 — ESPN team identity is not validated

Setup asks the user to type:

```text
My ESPN team id
```

as a number.

If it is:

- blank;
- wrong;
- stale;
- type-mismatched;

then every user's ESPN pick is classified as:

```text
gone
```

rather than:

```text
mine
```

The advisor will then believe the user's roster is empty through the entire draft.

This is a catastrophic failure mode with no strong warning.

## Required fix

After `Test once`, the adapter already returns team names.

Replace the numeric text field with a dropdown:

```text
1 — Team Name
2 — Team Name
...
```

Store a normalized string or number consistently.

Before enabling live mode:

```text
myTeamId must be present
myTeamId must exist in snapshot.teams
```

Fail closed otherwise.

## Also validate team count

The live snapshot already tells you how many ESPN teams exist.

If:

```text
ESPN teams != state.settings.teams
```

the board's snake math is wrong.

Do not silently continue.

Prompt:

```text
ESPN reports 10 teams but this board is configured for 12.
Use ESPN league size?
```

Ideally the Worker should normalize:

```js
settings.size
```

from `mSettings`.

---

# 7. P0 — manual and ESPN state still do not have a clean authority model

The README says manual marks and live ESPN state can coexist.

That is useful operationally, but the current merge rule can defeat the principal benefit of whole-snapshot reconciliation.

## 7.1 Provenance bug

Current logic marks a player as feed-owned only inside:

```js
if (p.status !== want || p.pickNo !== d.overall) {
    p.status = want;
    p.pickNo = d.overall;
    p.feed = true;
}
```

If a manual mark already exactly matches ESPN:

```text
same status
same pick number
```

`p.feed` is never set.

A later ESPN correction will not restore him.

### Fix

If a player is present in the authoritative snapshot, provenance should be set regardless of whether the visible state changed.

Better:

```js
p.draftSource = "espn";
```

Use an enum, not a Boolean.

---

## 7.2 `manualMax` prevents true ESPN self-healing

Current clock:

```js
state.nextPick = Math.max(
  espnNextPick,
  manualMax + 1
);
```

This means a manual sequence can keep the board ahead of ESPN even after a healthy ESPN feed returns.

That undermines:

> whole-snapshot reconciliation as the source of truth.

### Recommended authority rule

When the ESPN feed is healthy:

```text
ESPN snapshot owns:
- drafted players
- team ownership
- overall pick numbers
- next pick
```

Manual actions may be stored as:

```text
provisional overlays
```

while the feed is stale/disconnected.

When a healthy snapshot returns:

- confirmed provisional marks become ESPN-owned;
- contradicted provisional marks should be surfaced for review;
- ESPN clock becomes authoritative.

Do not allow manual pick chronology to permanently override a healthy snapshot.

---

# 8. P0 — only the advisor/Space path has an on-turn guard

The Space shortcut is fixed.

The primary advisor Draft button is only rendered when `onTheClock()`.

But the general board still has paths that can call:

```js
setStatus(id, "mine")
```

without an on-turn check.

Examples:

- every player's **Drafted** row button;
- Shift+Enter from search.

So the same class of state corruption can still happen from other controls.

## Required fix

Guard the mutation centrally.

For example:

```js
function draftMine(id, { force = false } = {}) {
    if (!force && !onTheClock()) {
        toast("It is not your pick.");
        return false;
    }
    ...
}
```

All UI paths call this function.

If a manual override is required:

```text
Hold Alt / confirm override
```

and label it as an override.

When a healthy ESPN feed is connected, consider disabling manual "mine" entirely and letting ESPN assign the user's roster.

---

# 9. P0 — polling has no timeout or single-flight guard

Current live loop:

```js
pollOnce();
setInterval(pollOnce, 3000);
```

and each `pollOnce()` performs a browser `fetch()` with no timeout.

If a request hangs longer than the interval:

```text
poll A starts
poll B starts
poll C starts
...
```

Multiple requests can overlap.

## Risks

- request pile-up;
- out-of-order responses;
- stale same-count snapshot applied after a newer response;
- unnecessary ESPN/Worker load;
- confusing status transitions.

The pick-count regression check catches only one class of out-of-order result.

Same-pick-count corrections can still be applied out of order.

## Required fix

Use both:

### Single flight

```js
if (feed.inFlight) return;
feed.inFlight = true;
try {
   ...
} finally {
   feed.inFlight = false;
}
```

### Abort timeout

Example:

```text
5–8 seconds
```

using `AbortController`.

Better yet, schedule the next poll with `setTimeout()` only after the prior poll completes.

---

# 10. P0/P1 — snapshot validation is too shallow

`validateSnapshot()` currently validates:

- object exists;
- no error;
- schema version;
- `picks` is an array.

It does **not** validate:

```text
draft exists
draft.pickCount
draft.nextOverallPick
overall pick uniqueness
playerId uniqueness
positive/integer overall values
pickCount == picks.length
duplicate overall picks
duplicate player picks
```

After validation returns, `pollOnce()` accesses:

```js
s.draft.pickCount
```

outside the initial fetch/parse try block.

Malformed adapter output can therefore cause an uncaught rejection rather than a clean Stale state.

## Fix

Validate the entire normalized contract before accepting it.

Fail closed and hold last good snapshot.

---

# 11. P0/P1 — the project silently assumes a snake redraft league

The browser's core timing model is:

```text
fixed snake
fixed slot
round reverses every round
```

The Worker already requests `mSettings`, but then discards the draft settings.

Current ESPN reverse-engineered documentation indicates that `mSettings` exposes:

```text
settings.draftSettings.type
settings.draftSettings.keeperCount
settings.draftSettings.pickOrder
```

and that `mDraftDetail` is also used for auction and keeper drafts.

Keeper entries may already appear in the pick list before the live draft.

## Required policy

If this product is for one known standard snake redraft league, that is fine.

Then explicitly validate and fail closed:

```text
draft type = SNAKE
keeperCount = 0
team count matches
```

If it is intended to be general, those modes require actual support.

## Worker improvement

Normalize:

```json
{
  "league": {
    "size": 12,
    "draftType": "SNAKE",
    "keeperCount": 0,
    "pickOrder": [...]
  }
}
```

The board can then validate itself before Connect.

---

# 12. P0 — exported project layout does not match the README

The README describes:

```text
draft-room-pro.html
draft-board.html
worker/index.js
worker/wrangler.toml
tools/espn-draft-watch.py
2026-fantasy-football-draft-report.md
```

The exported ZIP actually contains only:

```text
draft-room-pro.html
index.js
espn-draft-watch.py
README.md
```

Missing as documented:

```text
draft-board.html
worker/index.js       (index.js exists at root instead)
worker/wrangler.toml
tools/espn-draft-watch.py  (script exists at root instead)
2026-fantasy-football-draft-report.md
```

As exported, the project cannot be followed literally from its own deployment instructions.

## Required release cleanup

Make the deliverable match the documentation.

Recommended:

```text
/
  README.md
  site/
    index.html
  worker/
    src/
      index.js
    wrangler.toml
    package.json
  tools/
    espn-draft-watch.py
  research/
    2026-fantasy-football-draft-report.md
```

or simplify the README to match the actual root layout.

Do not ship a README that refers to missing fallback/research/config files.

---

# 13. P1 — the 156-player board is too shallow for a 192-pick league

This is separate from the clock bug.

A draft assistant should contain more draftable players than the total number expected to be selected.

Recommended target:

```text
minimum 220
preferably 250–300
```

for a 12-team, 16-round redraft board.

Why:

- late-round recommendations remain meaningful;
- out-of-pool ESPN picks become exceptional rather than routine;
- sleeper coverage improves;
- manually added emergency players become less necessary.

The current pool is especially shallow at:

```text
QB 16
RB 38
```

for a league that will make 192 total selections.

## UI terminology

Until the pool is expanded, do not call every unknown ESPN player an:

```text
unmatched data-quality warning
```

Many will simply be legitimate **out-of-board picks**.

Distinguish:

```text
identity mismatch
```

from:

```text
player outside curated board
```

---

# 14. P1 — Queue currently reuses the sleeper/star toggle

Before the user's turn, the advisor's Queue button is implemented as:

```html
data-star="..."
```

Space before the turn also calls:

```js
toggleStar(p.id)
```

But `toggleStar()` treats an existing sleeper as already "on" and removes:

```js
p.sleeper = null
```

## Failure

If the projected top recommendation is a curated sleeper:

```text
press Queue
```

can erase his A/B/C sleeper designation instead of queueing him.

## Fix

Create a separate field:

```js
queued: true | false
```

Queue and sleeper research are different concepts.

A queued player may also be a sleeper.

---

# 15. P1 — forecast scoring is not fully conditioned on reaching the upcoming user pick

The UI now correctly displays:

```text
X% reaches my upcoming pick
```

when the user is not currently on the clock.

However, `scorePlayer()` still calculates:

```js
expectedBestAt(pos, win.next)
survival(p, win.next)
```

with conditioning defaulting to:

```text
state.nextPick
```

rather than:

```text
win.now
```

for the forecast decision.

So the projected card mixes two questions:

1. will he reach my upcoming pick?
2. if he reaches my upcoming pick, how urgent is he relative to my following pick?

Those should be separated.

## Better forecast

When not on the clock:

```text
reach = P(player reaches win.now | available now)

conditional next-turn survival =
P(player reaches win.next | player reached win.now)
```

Then either:

```text
forecast score = score as of win.now, if available
```

and label clearly **IF AVAILABLE**,

or calculate expected forecast utility weighted by `reach`.

Do not treat the current-state urgency as though the user can draft the player now.

---

# 16. P1 — score still contains correlated/double-counted terms

Current score combines:

```text
base
VOR
urgency
tier cliff
market edge
```

Most are derived from the same source rank utility.

Specifically:

```text
base    = rank utility
VOR     = base - replacement
urgency = base - expected future base
cliff   = rank-utility difference
```

Then the whole result is multiplied by roster need.

This can create false precision.

## Observed default behavior

In a synthetic default 12-team state at pick 1.03 with Gibbs and Bijan already gone, the engine ordered approximately:

```text
1. Ja'Marr Chase        source #3
2. Jaxon Smith-Njigba  source #5
3. Puka Nacua          source #6
4. Amon-Ra St. Brown   source #8
5. Jonathan Taylor     source #4
```

This is not automatically wrong in a three-WR half-PPR style league.

But it demonstrates that the combination of:

- WR replacement;
- three unfilled WR starters;
- need multiplier;
- VOR;
- base;
- urgency;

is strong enough to move several lower source-ranked WRs ahead of a higher-ranked foundational RB.

That behavior needs to be **validated**, not assumed.

## Recommendation

Before hand-tuning weights further, compare against simpler formulations:

### Baseline A

```text
source ranking
```

### Baseline B

```text
VOR only
```

### Baseline C

```text
VOR + conditional VONA
```

### Current

```text
VOR + VONA + base + tier + edge × need
```

If the current extra terms do not improve replay outcomes, remove them.

---

# 17. P1 — early-draft need multiplier likely double-counts roster demand

Replacement level already incorporates league demand.

Example:

```text
3 starting WR
2 starting RB
1 FLEX
```

changes the WR/RB replacement thresholds.

Then `needFactor()` gives an additional early-draft multiplier based on how many dedicated starting slots are unfilled.

At the beginning:

```text
WR need > RB need
```

because three WR slots are empty versus two RB slots.

This is likely counting lineup demand twice.

## Cleaner alternative

Keep `need = 1.0` through most of the draft.

Use roster construction primarily through:

```text
replacement / marginal lineup value
```

Then escalate need only when:

```text
remaining picks are approaching required holes
```

The existing `lineupHoles()` framework is already a good basis for this.

---

# 18. P1 — VONA should use marginal value, not raw base value

Current:

```js
vor = max(0, base - replacement)

later = expectedBestAt(...)
urgency = max(0, base - later)
```

If the expected future player is below replacement, `urgency` can represent loss in raw rank utility below the point where the roster no longer gains starter value.

A cleaner formulation:

```text
currentMarginal = max(0, currentBase - replacement)

futureMarginal =
max(0, expectedFutureBase - replacement)

VONA =
max(0, currentMarginal - futureMarginal)
```

This also reduces some double counting between VOR and urgency.

---

# 19. P1 — fixed FLEX shares remain a heuristic

The project still uses:

```js
RB: 0.45
WR: 0.45
TE: 0.10
```

for replacement calculations.

This is acceptable as an interim approximation.

It is not league-derived.

## Better solution

1. allocate all dedicated starters;
2. take the remaining eligible RB/WR/TE population;
3. fill the league-wide FLEX demand from the best remaining marginal values;
4. derive the actual positional share from that allocation.

Then FLEX scarcity comes from the player pool rather than a fixed assumption.

---

# 20. P1 — no-ADP probabilities should not be displayed as real confidence

Current fallback:

```text
K/DST: 97%
other unpriced player: 60%
```

regardless of whether the target is:

```text
2 picks away
or
100 picks away
```

This should not be shown as a precise probability.

## Options

### Preferred

Use:

```text
N/A
```

for survival when no market estimate exists.

### Better data option

The ESPN player pool exposes ownership/ADP information in known response schemas.

Use ESPN ADP as a fallback for players without the curated multi-site ADP.

Keep source labels:

```text
ADP source: curated
ADP source: ESPN fallback
```

---

# 21. P1 — rankings refresh still does not do what its copy says

Setup says:

> rank, ADP, tier, bye and team update in place

The parser returns:

```text
rank
name
pos
team
bye
adp
```

There is no tier field.

`applyRankings()` never updates tier.

## Additional parser problem: decimal ADP

Numeric parsing currently accepts only:

```regex
^\d{1,3}$
```

So:

```text
ADP 27.4
```

is not parsed as a number.

Many real ADP sources use decimals.

This is especially important because ADP powers the survival model.

## Required fix

Use header-aware parsing rather than relying on "first number / last number."

Support:

```text
rank
player
position
team
bye
tier
adp
```

and decimal ADP.

If tier is not supported, remove it from the UI promise.

---

# 22. P1 — `offBoard` does not migrate or refresh safely

Fresh seed:

```js
offBoard: r[3] >= 999
```

Good.

But:

- old saved states may not contain `offBoard`;
- `migrate()` does not add it;
- `applyRankings()` can change `ovr` without updating `offBoard`.

## Failure examples

### Old saved state

Josh Jacobs can load without explicit `offBoard`.

### Player reinstated

Rank changes from:

```text
999 -> 60
```

but `offBoard` remains true.

### Player removed

Rank changes:

```text
60 -> 999
```

but `offBoard` remains false.

## Fix

Prefer a real source field:

```js
eligibility:
  "active"
  "excluded"
  "suspended"
  "unknown"
```

If continuing to infer:

```js
p.offBoard = p.ovr >= 999
```

do it in migration and refresh.

---

# 23. P1 — off-board affects the engine but not the manual UI

`engineAvail()` excludes `offBoard`.

The normal board's `availIn()` does not.

Therefore an off-board player can still appear as:

```text
available
```

and can still be manually drafted.

This may be intended as an override.

If so, make it explicit:

```text
Excluded — override
```

instead of representing him exactly like a normal available player.

---

# 24. P1 — stable identity should ultimately be ESPN ID

The board still creates synthetic IDs:

```text
p1
p2
p3
...
```

and separately stores:

```text
espnId -> boardId
```

This works for one build.

It becomes fragile across seed edits, resets, and persisted maps.

Long term:

```js
id: "espn:4430807"
espnId: 4430807
```

should be the canonical ID for ESPN players.

Custom manually added players can use:

```text
custom:<uuid>
```

Names become display metadata, not identity.

---

# 25. P1 — live league settings should validate the board automatically

The Worker already requests `mSettings`.

Use it.

Useful fields include:

```text
settings.size
settings.draftSettings.type
settings.draftSettings.keeperCount
settings.draftSettings.pickOrder
settings.rosterSettings.lineupSlotCounts
settings.scoringSettings
```

The board should compare ESPN versus local Setup before live mode.

Examples:

```text
Board: 12 teams
ESPN: 10 teams
```

or:

```text
Board: 1 QB / 2 RB / 3 WR
ESPN roster slots disagree
```

This should be a visible validation warning.

The goal is to eliminate manual misconfiguration.

---

# 26. P1 — scoring format is still implicit

Setup changes lineup configuration, but not fantasy scoring.

The engine assumes source rankings already encode the intended scoring format.

That is acceptable for a one-league personal board **if it is documented**.

It is not a generic league optimizer.

The project should state the exact supported ranking/scoring context, for example:

```text
2026 redraft
half-PPR
1QB
...
```

If the user wants the board configurable across formats, player projections or format-specific rankings need to be switched too.

Changing the number of starting WRs does not convert a half-PPR ranking into full PPR.

---

# 27. P1 — `/api/players` failures need better classification

The Worker classifies all non-OK player lookup responses as:

```text
upstream
```

rather than distinguishing:

```text
auth
config
rate limit
```

The browser then interprets a non-OK response as:

> adapter has no `/api/players` route

which may be false.

Improve the Worker response classification and show the actual reason.

---

# 28. P1 — validate partial cookie configuration in the Worker

Worker currently sends cookies only if:

```js
env.ESPN_SWID && env.ESPN_S2
```

If only one secret is configured, it silently behaves like a public-league request.

The Python tool correctly rejects this configuration.

The Worker should too.

Example:

```text
ESPN_SWID set
ESPN_S2 missing
```

should return:

```text
config error: set both or neither
```

---

# 29. P1/P2 — default three-second ESPN polling is aggressive

Cloudflare capacity is not the concern.

Current Cloudflare documentation still shows Workers Free at:

```text
100,000 requests/day
10 ms CPU per invocation
```

So a three-hour draft at one poll every three seconds is comfortably below the request limit.

The risk is the unofficial ESPN endpoint.

Current community documentation for `mDraftDetail` recommends polling on the order of **10–30 seconds** during a live draft.

That guidance is not official ESPN policy, but it is a useful caution.

## Better policy

Adaptive polling:

```text
not near my pick: 8–10s
2–3 picks away:   3–5s
my pick:          2–3s
error/429:        exponential backoff
```

Because the feed is whole-snapshot reconciled, slower background polling does not lose state.

---

# 30. P2 — observed room behavior should eventually modify survival

Once ESPN integration works, the board knows:

- which positions are running;
- which managers pick before the user;
- how the room is deviating from ADP.

A future improvement should update survival with:

```text
room positional acceleration
```

Example:

```text
RBs are being selected 6 picks earlier than market
```

Shift remaining RB survival earlier.

This is likely more valuable than adding another fixed score weight.

---

# 31. P2 — two-turn rollout is still the best next intelligence upgrade

After the deterministic engine is correct:

For every candidate at the user's pick:

1. assume candidate is drafted;
2. simulate the intervening selections;
3. select the best option at the next user pick;
4. compare the two-player package.

This directly evaluates:

```text
Player A now + likely Player B later
versus
Player C now + likely Player D later
```

That is more actionable than adding more correlated terms to one static score.

Do this before full-rest-of-draft Monte Carlo.

---

# 32. P2 — projections should eventually replace rank utility

Current engine is honest:

```text
rank utility != projected points
```

Keep that honesty.

Long term:

```text
league-scored projected points
-> replacement value
-> marginal starter value
```

is more defensible than converting overall rank through an arbitrary exponential curve.

ADP remains the market timing signal.

---

# 33. Python diagnostic client review

`espn-draft-watch.py` is much improved.

Good:

- correct current read host;
- standard library only;
- normalized contract;
- classified errors;
- exponential retry/backoff;
- last-good snapshot retained;
- atomic output file;
- player ID end to end;
- completion fields preserved separately.

## Remaining minor issue: corrected pick logging

The console's `seen` set is keyed only by:

```text
overall pick number
```

If ESPN corrects pick 42 from Player A to Player B:

- normalized snapshot/output file are correct;
- console "new pick" log will not announce the correction because overall 42 was already seen.

Use:

```text
overall -> playerId/teamId fingerprint
```

instead of only a set.

This is diagnostic-only and not a browser blocker.

## JSON stream note

`--json` without `--once` produces successive pretty-printed JSON documents.

That is fine for human diagnostics but is not one valid JSON document.

If machine streaming is intended later, use NDJSON.

---

# 34. Worker review

The Worker architecture remains sound:

```text
browser
-> Worker
-> ESPN
```

Secrets stay server-side.

The current ESPN read host is correct.

The normalized `mDraftDetail` fields used by the project match current reverse-engineered documentation.

## Add to the normalized schema

Recommended:

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

and preserve:

```text
keeper
```

on each pick.

This lets the browser reject unsupported configurations before they damage state.

---

# 35. Security review

No actual credentials were found in the export.

Good:

- SWID/S2 are environment/Worker secrets;
- no browser cookies;
- no LLM keys;
- worker logs diagnostics only;
- README warns CORS is not authentication.

## ALLOWED_ORIGIN documentation

Clarify that an origin is:

```text
https://username.github.io
```

not:

```text
https://username.github.io/repository/path
```

Origin matching does not include the URL path.

## Public Worker endpoint

Anyone who knows the Worker URL can request it outside a browser regardless of CORS.

The README already acknowledges this general tradeoff.

That is acceptable for a personal draft-state endpoint if the user is comfortable with it.

---

# 36. Release checklist

I would not deploy for a real draft until all items marked **BLOCK** pass.

## Feed/state

- [ ] **BLOCK** unmatched pick updates visible/persisted clock
- [ ] **BLOCK** identity resolution must succeed before live mode
- [ ] **BLOCK** my ESPN team ID selected/validated
- [ ] **BLOCK** ESPN team count validated against board
- [ ] **BLOCK** manual-confirmed pick becomes ESPN-owned
- [ ] **BLOCK** healthy ESPN feed owns the clock
- [ ] **BLOCK** all "draft to my team" paths centrally enforce turn
- [ ] **BLOCK** polling single-flight + timeout
- [ ] **BLOCK** full snapshot shape validation
- [ ] **BLOCK** reject/warn unsupported auction/keeper configuration

## Deployment

- [ ] **BLOCK** ZIP layout matches README
- [ ] **BLOCK** include `wrangler.toml` or correct deployment instructions
- [ ] verify Worker secrets with real private/public league
- [ ] verify CORS against actual GitHub Pages origin
- [ ] test direct page reload restores local state

## Mock draft

- [ ] run a real ESPN mock draft
- [ ] verify REST `mDraftDetail` latency
- [ ] leave tab open through network interruption
- [ ] intentionally miss several polls
- [ ] force an unmatched/out-of-pool pick
- [ ] verify user's picks become `mine`
- [ ] verify opponent picks become `gone`
- [ ] disconnect/reconnect
- [ ] reload the browser mid-draft
- [ ] test ESPN correction if mock environment permits
- [ ] test Worker 401/403 behavior with invalid credentials
- [ ] test 429/backoff behavior

## Data/model

- [ ] expand curated pool beyond 192 players
- [ ] separate Queue from Sleeper
- [ ] support decimal ADP
- [ ] fix/remove claimed tier refresh
- [ ] migrate/update `offBoard`
- [ ] decide whether manual positional re-ranking influences advisor
- [ ] replace no-ADP fake probabilities
- [ ] calibrate need multiplier/double counting
- [ ] compare current model against simpler VOR/VONA baselines

---

# 37. Suggested implementation order

## Pass 1 — live-state correctness

Do these together:

```text
unmatched clock render
team identity validation
feed ownership/provenance
ESPN authoritative clock
central manual turn guard
poll single-flight/timeout
full validation
draft-type/keeper validation
```

Then run a mock draft.

## Pass 2 — deployment/package

Make the ZIP/repository match README exactly.

Deploy actual Pages + Worker.

Run another mock draft through the deployed URLs, not local files.

## Pass 3 — data integrity

Fix:

```text
pool depth
decimal ADP
tier refresh
offBoard migration
Queue state
ESPN-ID canonical identity
```

## Pass 4 — model calibration

Do not add new terms first.

Test:

```text
source rank
VOR
VOR + conditional VONA
current weighted model
```

against replay scenarios.

## Pass 5 — smarter drafting

Then add:

```text
projections
room-adjusted survival
opponent roster modeling
two-turn rollout
```

---

# 38. Final assessment

The project is significantly better than the version reviewed previously.

The earlier architectural recommendations were not just cosmetically added. Several were implemented correctly:

- local browser persistence;
- conditional survival;
- engine/UI separation;
- derived caps;
- FLEX forced-fill handling;
- forecast mode;
- snapshot reconciliation;
- server-side ESPN credential handling.

That is real progress.

The remaining P0s are concentrated enough that I would **fix them rather than redesign anything**.

My target before calling this draft-night ready is:

```text
ESPN snapshot is authoritative
+
every accepted snapshot visibly advances the board
+
identity/team config cannot silently fail
+
manual fallback cannot poison live chronology
+
one request at a time
+
unsupported league modes fail closed
```

Once those are true, I would be comfortable moving from "prototype with strong logic" to **draft-night beta**.

After a successful real ESPN mock draft, the biggest remaining question becomes the recommendation model itself, especially:

```text
Does the weighted model consistently beat
a simpler VOR + conditional VONA baseline?
```

That is the next debate worth having.

Do not spend another cycle redesigning the interface.
