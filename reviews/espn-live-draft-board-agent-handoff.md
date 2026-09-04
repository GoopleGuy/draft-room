# ESPN Live Draft Board Integration
## Technical Review, Agent Handoff, and Recommended V2 Architecture

**Prepared:** 2026-09-03  
**Current script reviewed:** `espn-draft-watch.py`  
**Target:** A live ESPN fantasy-football draft feed powering an intelligent selection board, with the board ultimately hosted on GitHub Pages.

---

# 1. Executive summary

The core concept is viable: ESPN's unofficial Fantasy API exposes live draft state through the `mDraftDetail` view, including the ordered list of picks and the ESPN `playerId` and `teamId` associated with each pick.

The current Python script is a useful proof of concept, but it is not the architecture that should be shipped. It has two concrete implementation problems and a larger architectural mismatch with the final deployment target:

1. **The production ESPN hostname is wrong in the current script.**
   - Current: `https://lm-api-reads.espn.com/...`
   - Recommended production host: `https://lm-api-reads.fantasy.espn.com/...`
   - `https://fantasy.espn.com/...` is also documented by current community references as a usable/legacy Fantasy endpoint.

2. **The script tries to discover player names from roster data without requesting `mRoster`.**
   - It requests `mDraftDetail`, `mTeam`, and `mSettings`.
   - `mTeam` supplies team metadata.
   - `mRoster` is the view that adds `teams[].roster.entries[]`.
   - The current `index_players()` function therefore depends on data the request does not explicitly ask ESPN to return.

3. **Even after those fixes, the script does not actually provide live data to the board.**
   - It polls ESPN.
   - It prints new picks.
   - It rewrites `drafted.txt`.
   - The user must still manually paste that list into the board.

4. **GitHub Pages cannot execute this Python poller.**
   - GitHub Pages is static hosting and does not support server-side Python.
   - Private-league ESPN cookies must not be embedded in client-side JavaScript hosted on Pages.

The recommended final design is therefore:

```text
ESPN Fantasy API
      |
      | authenticated server-side request
      v
Small serverless ESPN proxy / adapter
      |
      | normalized JSON only
      v
GitHub Pages selection board
      |
      +--> draft-state reducer
      +--> drafted-player set
      +--> roster reconstruction
      +--> recommendation/scoring engine
      +--> UI
```

**Key design decision:** use **ESPN `playerId` as the canonical player identity** throughout the system. Do not make the live integration depend on matching player names as strings.

---

# 2. Intended product behavior

On draft night, the user should be able to open the selection board and leave it open for the entire ESPN draft.

When any team makes a pick in ESPN:

1. ESPN adds the pick to `draftDetail.picks`.
2. The backend proxy sees the new state on its next poll/request.
3. The board receives the updated normalized JSON.
4. The board adds that ESPN `playerId` to its drafted set.
5. The selected player disappears from available-player rankings.
6. The board reconstructs the user's roster if the pick belongs to the configured user team.
7. Positional scarcity, tier pressure, roster need, opponent behavior, and other recommendation inputs are recalculated.
8. The UI updates automatically without a manual refresh or paste operation.

A reasonable target is **roughly 2-5 seconds from an ESPN pick to the board reflecting it**, while tolerating temporary network failures without losing the last known good draft state.

---

# 3. Review of the current `espn-draft-watch.py`

## What the current script gets right

The current script has several good ideas worth preserving:

- Uses ESPN's v3 league API rather than scraping HTML.
- Uses `mDraftDetail` to obtain draft picks.
- Correctly repeats `view` query parameters rather than comma-joining them.
- Supports both public and private leagues.
- Keeps `SWID` and `espn_s2` outside source code through environment variables.
- Uses a browser-like `User-Agent` and JSON `Accept` header.
- Sorts picks by `overallPickNumber`.
- Uses `overallPickNumber` to detect picks not previously seen.
- Keeps the polling interval configurable.
- Does not actually require the third-party `requests` package; the implementation uses the Python standard library.

These are good foundations for a local diagnostic tool.

---

# 4. Concrete problems in the current script

## 4.1 Production hostname is incorrect

Current code:

```python
BASE = ("https://lm-api-reads.espn.com/apis/v3/games/ffl"
        "/seasons/{season}/segments/0/leagues/{league}")
```

Recommended:

```python
BASE = ("https://lm-api-reads.fantasy.espn.com/apis/v3/games/ffl"
        "/seasons/{season}/segments/0/leagues/{league}")
```

Current community-maintained OpenAPI/reference material identifies `lm-api-reads.fantasy.espn.com` as the Fantasy API production server.

This should be treated as a blocking correction before testing the present watcher.

---

## 4.2 Player-name lookup and requested views do not line up

The request asks for:

```text
view=mDraftDetail
view=mTeam
view=mSettings
```

But `index_players()` contains:

```python
for team in blob.get("teams") or []:
    entries = ((team.get("roster") or {}).get("entries")) or []
```

Current reverse-engineered documentation distinguishes these views:

- `mTeam` -> team names, owners, records, etc.
- `mRoster` -> `teams[].roster.entries[]`
- `mDraftDetail` -> `draftDetail.picks[]`

Therefore the script may successfully detect a pick but fail to resolve the pick's name, falling back to:

```text
player #1234567
```

### Do not solve this merely by adding `mRoster` to every live poll

Adding `mRoster` would make the present implementation more internally consistent, but it is not the best final design. `mRoster` is much heavier than `mDraftDetail`, and during the draft the only live identity we truly need from ESPN is `playerId`.

**Recommended design:** the board's player dataset should already have an ESPN ID for each player. Then live picks are matched by numeric ID, not by names retrieved from the live response.

---

## 4.3 The current script is a watcher, not an integration

Current flow:

```text
ESPN -> Python watcher -> console + drafted.txt -> manual paste -> board
```

This does not meet the intended end state of a self-updating board.

The `drafted.txt` output is useful only as:

- a development fallback,
- a manual emergency mode,
- or a diagnostic artifact.

It should not be the primary production data path.

---

## 4.4 Draft completion semantics should be more explicit

Current code:

```python
def picks_of(blob):
    dd = blob.get("draftDetail") or {}
    picks = dd.get("picks") or []
    return dd.get("drafted", False), picks
```

The variable receiving `drafted` is then named `complete`.

ESPN's `draftDetail` currently exposes distinct fields including:

- `drafted`
- `inProgress`
- `completeDate`
- `picks[]`

The adapter should preserve those semantics instead of treating `drafted` as synonymous with complete.

Recommended normalization:

```python
state = {
    "drafted": bool(dd.get("drafted")),
    "inProgress": bool(dd.get("inProgress")),
    "completeDate": dd.get("completeDate"),
    "picks": dd.get("picks") or [],
}
```

For UI purposes, `completeDate != null` is the clearest completion indicator when available.

---

## 4.5 One temporary transport failure kills the current watcher

The current `fetch()` exits the process on:

- HTTP errors,
- DNS/connectivity errors,
- invalid JSON.

That is acceptable for a one-shot utility but poor draft-night behavior.

Desired behavior:

- `401/403`: explicit authentication warning; retain last known board state.
- `404`: explicit configuration/season/league warning.
- `429`: back off and retry.
- `500/502/503/504`: retry with bounded exponential backoff.
- timeout/DNS/transient network error: retain last known good state and retry.
- malformed ESPN response: mark feed stale rather than clearing draft state.

The board should visibly display something like:

```text
LIVE FEED STALE
Last successful ESPN sync: 20:41:17
```

It should **never undraft players merely because a poll failed**.

---

## 4.6 The file rewrite is not atomic

Current code opens the output path with `"w"`, truncating it before rewriting the contents. A simultaneous reader can theoretically observe an empty or partially written file.

For a local fallback utility, write to a temporary file and use `os.replace()`.

This issue becomes irrelevant once the text file is removed from the primary architecture.

---

## 4.7 Setup documentation includes an unnecessary dependency

The header says:

```text
pip install requests
```

The script does not import or use `requests`.

The current watcher is standard-library-only.

---

# 5. Recommended V2 architecture

## 5.1 Responsibilities should be separated

### A. ESPN adapter / proxy

Its job should be intentionally boring:

- keep ESPN credentials secret,
- call ESPN,
- validate enough of the response to detect bad upstream state,
- normalize the data,
- return small JSON,
- optionally cache for a very short interval,
- return clear health/staleness information.

It should **not** make fantasy-football recommendations.

### B. GitHub Pages frontend

The frontend owns:

- the player database,
- ESPN-ID-to-player lookup,
- drafted-player state,
- team/roster reconstruction,
- tiers/rankings/ADP/projections,
- recommendation calculations,
- UI state,
- displaying feed health.

### C. Optional LLM service

If the shipped application calls Claude/Anthropic or another LLM at runtime, that request must also pass through a backend/serverless service so the API key is not exposed in the static site.

The recommendation engine should ideally remain deterministic/local for its primary ranking. An LLM can be used for explanations, scenario analysis, or tie-breaking, but should not be required for the board to function during a draft.

---

# 6. Recommended deployment topology

## Preferred simple version

```text
+------------------------------------------------------+
| GitHub Pages                                         |
|                                                      |
| index.html / JS / CSS                                |
| player-data.json                                     |
| rankings / tiers / projections                       |
| recommendation engine                                |
| live draft state reducer                             |
+------------------------------+-----------------------+
                               |
                               | GET /api/draft
                               | every ~2-5 sec
                               v
+------------------------------------------------------+
| Serverless ESPN adapter                              |
| Recommended: Cloudflare Worker                       |
| Alternatives: Vercel Function / Netlify / other      |
|                                                      |
| Secrets:                                             |
|   ESPN_SWID                                          |
|   ESPN_S2                                            |
| Config:                                              |
|   ESPN_LEAGUE_ID                                     |
|   ESPN_SEASON                                        |
|   allowed GitHub Pages origin                        |
+------------------------------+-----------------------+
                               |
                               | server-side request
                               v
+------------------------------------------------------+
| ESPN Fantasy API                                     |
| lm-api-reads.fantasy.espn.com                        |
| view=mDraftDetail                                    |
| optionally view=mTeam / view=mSettings               |
+------------------------------------------------------+
```

### Why Cloudflare Worker is a good fit

For this specific application it is attractive because:

- the proxy logic is tiny,
- secrets can be stored server-side,
- deployment is easy,
- request latency is low,
- a short edge cache can prevent duplicate ESPN requests if multiple browser tabs are open,
- no always-on server is required.

Using Python is not a requirement for the final product. The current Python script is best viewed as a diagnostic/prototyping client.

---

# 7. Canonical identity: ESPN player ID

This is one of the most important choices in the design.

Every player in the board's player dataset should contain something equivalent to:

```json
{
  "espnId": 4430807,
  "name": "Example Player",
  "position": "WR",
  "nflTeam": "XXX",
  "rank": 21,
  "tier": 3,
  "adp": 24.8
}
```

The live feed then sends only the ESPN ID associated with the pick.

The board performs:

```javascript
const draftedIds = new Set(feed.picks.map(p => p.playerId));
```

and availability becomes:

```javascript
const available = players.filter(p => !draftedIds.has(p.espnId));
```

### Benefits

- no name spelling ambiguity,
- no suffix problems (`Jr.`, `II`, `III`),
- no punctuation normalization,
- no collisions between similarly named players,
- no dependence on `mRoster` just to learn player names,
- faster/smaller live payloads,
- straightforward roster reconstruction.

If the current board dataset lacks ESPN IDs, adding them is a prerequisite for the robust live integration.

---

# 8. The draft feed can reconstruct rosters without `mRoster`

Each draft pick currently contains at least the key fields:

```json
{
  "playerId": 4430807,
  "teamId": 5,
  "overallPickNumber": 17,
  "roundId": 2,
  "roundPickNumber": 5
}
```

Because every pick includes `teamId`, the board can reconstruct every team's drafted roster directly from draft history:

```javascript
const rosters = new Map();

for (const pick of feed.picks) {
  if (!rosters.has(pick.teamId)) rosters.set(pick.teamId, []);
  rosters.get(pick.teamId).push(playersByEspnId.get(pick.playerId));
}
```

This means the live-draft loop can remain based primarily on `mDraftDetail`.

`mTeam` can be fetched when needed to map team IDs to names. `mSettings` can be fetched at startup/configuration time rather than necessarily on every 2-second live request.

---

# 9. Proposed normalized API contract

The frontend should not consume ESPN's undocumented raw response directly. Give the board a stable internal contract.

Recommended shape:

```json
{
  "schemaVersion": 1,
  "source": "espn",
  "season": 2026,
  "leagueId": "1234567",
  "observedAt": "2026-09-03T20:41:17.123Z",
  "healthy": true,
  "stale": false,
  "draft": {
    "drafted": true,
    "inProgress": true,
    "completeDate": null,
    "pickCount": 17,
    "nextOverallPick": 18
  },
  "picks": [
    {
      "id": 17,
      "overall": 17,
      "round": 2,
      "roundPick": 5,
      "teamId": 5,
      "playerId": 4430807,
      "bidAmount": 0,
      "autoDrafted": false
    }
  ]
}
```

Optional team metadata:

```json
{
  "teams": {
    "1": { "name": "Team One" },
    "2": { "name": "Team Two" }
  }
}
```

Do not return ESPN cookies or raw request headers under any circumstances.

---

# 10. Recommended backend behavior

## Request path

```text
GET /api/draft
```

## Upstream ESPN request

Preferred minimal live request:

```text
GET https://lm-api-reads.fantasy.espn.com/apis/v3/games/ffl/seasons/{season}/segments/0/leagues/{leagueId}?view=mDraftDetail
```

For team names/config, either:

```text
?view=mDraftDetail&view=mTeam&view=mSettings
```

or fetch the relatively static data separately and cache it longer.

## Headers

Use at least:

```text
Accept: application/json
User-Agent: normal application/browser-like UA
Cookie: SWID=...; espn_s2=...
```

The Cookie header is required only for private leagues.

## Normalization

The adapter should:

1. Require `draftDetail` to be an object.
2. Require `draftDetail.picks` to be an array when present.
3. Sort by `overallPickNumber`.
4. Ignore malformed pick entries rather than corrupting the entire feed.
5. Preserve the ESPN numeric player and team IDs.
6. Calculate `pickCount` and `nextOverallPick`.
7. Return an explicit schema version.

## Caching

A 1-2 second cache is reasonable if multiple browser tabs/devices may hit the proxy.

Avoid long CDN caching. This is live state.

## CORS

Allow the actual GitHub Pages origin, for example:

```text
Access-Control-Allow-Origin: https://USERNAME.github.io
```

Do not use permissive credential forwarding from the browser. The browser should never possess ESPN credentials.

---

# 11. Frontend polling model

A simple poll loop is appropriate and easier to make reliable than WebSockets for an unofficial polling upstream.

Pseudo-code:

```javascript
let lastGoodFeed = null;
let consecutiveFailures = 0;

async function refreshDraft() {
  try {
    const response = await fetch(DRAFT_API_URL, { cache: "no-store" });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);

    const feed = await response.json();
    validateFeed(feed);

    consecutiveFailures = 0;
    lastGoodFeed = feed;
    applyDraftFeed(feed);
    setFeedStatus("live", feed.observedAt);
  } catch (err) {
    consecutiveFailures += 1;
    // IMPORTANT: do not clear lastGoodFeed or restore players to available.
    setFeedStatus("stale", lastGoodFeed?.observedAt, err);
  }
}

setInterval(refreshDraft, 3000);
refreshDraft();
```

### Idempotence matters

The board should derive drafted state from the entire current pick list rather than relying exclusively on one-time `new pick` events.

Good:

```javascript
const draftedIds = new Set(feed.picks.map(p => p.playerId));
```

Fragile:

```javascript
onNewPick(pick) {
  permanentlyMutatePlayer(pick);
}
```

Using the complete snapshot makes reloads, missed polls, and short outages self-healing.

---

# 12. Recommendation engine architecture

The live feed should supply facts. The selection engine should produce recommendations from those facts.

Recommended pipeline:

```text
Static player model
  - ESPN ID
  - name / position / NFL team
  - baseline rank
  - projections
  - ADP
  - tier
  - upside / floor or other model inputs

                 +

Live draft state
  - drafted IDs
  - my roster
  - opponent rosters
  - current overall pick
  - picks until my next selection

                 +

League configuration
  - roster slots
  - scoring
  - number of teams
  - draft type/order

                 v

Deterministic recommendation engine
  - remove drafted players
  - roster-need adjustment
  - positional scarcity
  - tier-drop risk
  - ADP reach/value
  - expected availability at next pick
  - stacking/correlation rules if desired
  - user-specific strategy constraints

                 v

Ranked candidates
  1. Best recommendation
  2. Alternative
  3. Upside choice
  4. Safe/value choice

                 +

Optional LLM explanation layer
```

## Strong recommendation

Do **not** make a runtime LLM call the single source of truth for whether a player is available or for basic score calculation.

The deterministic engine should remain functional if the AI service is down.

An LLM is excellent for output such as:

```text
Take Player A over Player B because the final Tier-2 WR is likely to disappear
before your next pick, while six comparable RBs remain in the same projection band.
```

It should be an interpretation layer over already-correct state.

---

# 13. Security requirements

## Never put these in GitHub Pages source

- `ESPN_SWID`
- `ESPN_S2`
- Anthropic/Claude API key
- any other private API key

Anything shipped to GitHub Pages is effectively public to a visitor through browser developer tools or repository/source inspection.

## Store ESPN credentials as server-side secrets

Examples:

- Cloudflare Worker secrets
- Vercel environment variables
- equivalent serverless secret store

## Repository hygiene

Include `.env` and local secret files in `.gitignore`.

Do not commit cookies even to a private repository if they can instead be injected at runtime.

## Public proxy visibility

Restrict browser CORS to the board's origin. Remember that CORS is a browser control, not strong authentication against arbitrary non-browser clients.

For a personal draft board, returning only normalized pick IDs through a public-but-obscure endpoint may be an acceptable risk. If private league information must be truly access-controlled, put authentication/access control in front of the proxy.

---

# 14. Reliability requirements for draft night

The board should follow these principles:

## Never roll back live state because of a failed poll

If the last successful response showed 37 picks and ESPN is temporarily unavailable, continue showing 37 drafted players.

## Detect suspicious regressions

If a later ESPN response unexpectedly contains fewer picks than the last successful one during an active draft, do not immediately accept the regression. Mark the feed suspicious/stale and retry.

Exception: a deliberate draft reset would need an explicit reset control.

## Display health visibly

Recommended indicators:

```text
LIVE - synced 1.2 sec ago
STALE - last successful sync 18 sec ago
AUTH ERROR - ESPN credentials need refresh
CONFIG ERROR - league/season not found
DRAFT COMPLETE - 180 picks
```

## Manual override must remain available

Even with a good API integration, keep a quick manual `mark drafted / undo` control in the UI. ESPN is undocumented and can change without notice.

## Log enough to diagnose problems

Backend logs should include:

- timestamp,
- upstream HTTP status,
- latency,
- pick count,
- whether draft is in progress,
- sanitized error type.

Never log cookie values.

---

# 15. Development bridge: how to improve the existing Python watcher

The present watcher remains useful as an independent test harness before wiring the browser to a serverless proxy.

Minimum fixes for a local V1.1 watcher:

1. Replace the hostname with `lm-api-reads.fantasy.espn.com`.
2. Stop advertising `pip install requests` unless the implementation actually changes to `requests`.
3. Preserve `drafted`, `inProgress`, and `completeDate` separately.
4. Add transient retry/backoff instead of exiting on every network problem.
5. If human-readable names are still required locally:
   - request `mRoster`, **or preferably**
   - load a local `espnId -> player metadata` map shared with the board.
6. Write `drafted.txt` atomically if the fallback file remains.
7. Add JSON output mode so the watcher can act as a debugging oracle for the normalized feed.

Suggested diagnostic command behavior:

```text
python espn-draft-watch.py --once --json
```

should emit the same normalized schema expected by the frontend.

That gives the project one canonical representation regardless of whether the ESPN adapter is temporarily local Python or deployed serverless code.

---

# 16. Proposed repository layout

One reasonable structure:

```text
/
|-- index.html
|-- css/
|   `-- app.css
|-- js/
|   |-- app.js
|   |-- draft-feed.js
|   |-- draft-state.js
|   |-- recommendation-engine.js
|   `-- ui.js
|-- data/
|   |-- players.json
|   |-- rankings.json
|   `-- league-config.json
|-- tools/
|   `-- espn-draft-watch.py
|-- worker/
|   |-- src/
|   |   `-- index.js
|   `-- wrangler.toml
|-- docs/
|   `-- espn-live-draft-integration.md
|-- .gitignore
`-- README.md
```

Do not put secret values in `league-config.json` or any other Pages-served file.

---

# 17. Suggested implementation phases

## Phase 1 - prove ESPN live state

- Fix the current watcher hostname.
- Point it at the real league.
- Run `--once` before the draft.
- Verify the shape of `draftDetail`.
- During a mock/test draft, verify that `picks` grows after each selection.
- Capture sanitized sample JSON for fixtures/tests.

## Phase 2 - canonical player IDs

- Add `espnId` to every player in the board dataset.
- Build `playersByEspnId`.
- Add automated checks for duplicate/missing IDs.
- Decide explicit handling for players not found in the board dataset.

## Phase 3 - normalized adapter

- Implement `/api/draft`.
- Store ESPN cookies as server-side secrets.
- Return the normalized contract in Section 9.
- Add response validation and sanitized errors.

## Phase 4 - frontend live-state reducer

- Poll the proxy every ~3 seconds.
- Derive `draftedIds` from the complete pick snapshot.
- Reconstruct all rosters by `teamId`.
- Update available-player rankings.
- Show feed health/staleness.

## Phase 5 - recommendation integration

- Recompute recommendation scores when the pick set changes.
- Do not rerun expensive calculations if a poll returns the same pick count/content hash.
- Highlight material recommendation changes after opponent selections.

## Phase 6 - optional AI layer

- Route runtime AI calls through a backend.
- Send only the structured state needed to explain/reason about the decision.
- Do not send ESPN cookies.
- Keep deterministic recommendations available as fallback.

## Phase 7 - draft-night hardening

- Simulate upstream 401, 429, 500, timeout, malformed JSON, and pick-count regression.
- Verify no player is accidentally returned to the available pool on a transient error.
- Verify manual override/undo.
- Verify page refresh reconstructs current state correctly.
- Test multiple open tabs.

---

# 18. Acceptance criteria

The integration should not be considered complete until all of the following are true.

## ESPN integration

- [ ] Correct Fantasy API hostname is used.
- [ ] Public league works without cookies if ESPN permits access.
- [ ] Private league works with server-side `SWID` and `espn_s2`.
- [ ] Credentials never appear in browser source, frontend network payloads, or logs.
- [ ] `mDraftDetail` returns live picks during a test/mock draft.

## Identity

- [ ] Each board player has a stable ESPN player ID.
- [ ] Drafted state is matched by ID, not by human-readable name.
- [ ] Unknown ESPN player IDs are shown as an explicit data-quality warning rather than silently ignored.

## Live behavior

- [ ] New ESPN selections appear automatically without user refresh.
- [ ] Missed polls self-heal from the next full pick snapshot.
- [ ] Temporary network failure does not erase draft state.
- [ ] Feed staleness is visible to the user.
- [ ] Draft completion is recognized correctly.

## Selection board

- [ ] Drafted players are automatically removed from availability.
- [ ] User roster is reconstructed from picks assigned to `MY_TEAM_ID`.
- [ ] Recommendations recompute only when draft state meaningfully changes.
- [ ] Manual mark-drafted and undo remain available.

## Deployment

- [ ] Static frontend is deployable to GitHub Pages.
- [ ] Server-side adapter is deployed somewhere that can keep secrets.
- [ ] CORS permits the Pages origin.
- [ ] No ESPN or LLM secret is committed to GitHub.

---

# 19. Recommended agent deliverables from here

The next implementation agent should produce, in this order:

1. **A corrected local ESPN diagnostic client** using the normalized schema.
2. **A captured/sanitized ESPN draft fixture** for automated frontend tests.
3. **An ESPN ID mapping audit** for the selection board's player dataset.
4. **A serverless `/api/draft` adapter**, preferably Cloudflare Worker unless another backend platform is already established.
5. **A frontend draft-state module** that consumes complete snapshots idempotently.
6. **A feed status component** showing live/stale/auth/config states.
7. **Integration with the existing recommendation engine** so a new pick invalidates/recalculates candidate scores.
8. **Failure-injection tests** for draft-night resilience.

The agent should avoid expanding scope into complex distributed infrastructure. For one live fantasy draft, a small stateless/short-cached adapter plus a deterministic browser-side state engine is enough.

---

# 20. Target end-state in one sentence

**GitHub Pages hosts the fast, local, intelligent draft board; a tiny secret-holding serverless adapter turns ESPN's unofficial live `mDraftDetail` response into stable normalized JSON; the board keys all player state by ESPN `playerId` and recomputes recommendations immediately whenever the draft snapshot changes.**

---

# 21. Sources / verification notes

These are unofficial ESPN API references because ESPN does not publish this Fantasy API as a supported public developer API. Re-verify before draft day because the API can change without notice.

- Public ESPN Fantasy API - draft endpoint and `draftDetail` fields:  
  https://github.com/pseudo-r/Public-ESPN-Fantasy-API/blob/main/docs/draft.md

- Public ESPN Fantasy API - view behavior and response schema:  
  https://github.com/pseudo-r/Public-ESPN-Fantasy-API/blob/main/README.md  
  https://github.com/pseudo-r/Public-ESPN-Fantasy-API/blob/main/docs/response_schemas.md

- Independently documented view behavior (`mTeam`, `mRoster`, `mDraftDetail`) and repeated `view` parameters:  
  https://github.com/DanielTomaro13/sportsdata-mcp/blob/main/documentation/ESPNFantasy.md

- Community OpenAPI specification identifying `lm-api-reads.fantasy.espn.com` as the production Fantasy server:  
  https://github.com/aaronweldy/espn-openapi/blob/main/spec-fantasy.yaml

- GitHub Pages limitation: no server-side Python/PHP/Ruby execution:  
  https://docs.github.com/en/pages/getting-started-with-github-pages/creating-a-github-pages-site

---

# 22. Notes to the implementation agent

Do not treat the current `drafted.txt` workflow as a requirement. It is a fallback from the prototype, not the desired integration boundary.

Do not solve player identity with fuzzy name matching unless absolutely necessary. The ESPN numeric player ID should be carried end-to-end.

Do not place ESPN cookies or an AI API key in the GitHub Pages application.

Do not make the board dependent on a successful poll every few seconds. Full snapshot reconciliation plus preservation of the last known good state is the intended failure model.

Before changing recommendation logic, first make the ingestion/state layer deterministic and testable. Once live state is trustworthy, the intelligent-selection logic can be improved independently without touching ESPN authentication or polling.
